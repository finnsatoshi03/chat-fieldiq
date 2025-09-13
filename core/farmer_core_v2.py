from dateutil.parser import parse
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from config.config import get_supabase_client
from core.company_core import Company
from exceptions.global_exception import GlobalException
from models.feed_calculator_model import CreateFeedCalculatorPayload, FeedCalculatorDto, UpdateFeedCalculatorPayload


class FarmerV2:
    def __init__(self):
        self.Client = get_supabase_client()
        self.Company = Company()

    # Create feed program
    def create_feed_program(self, farmer_user_profile_id: int, feed_product_id: int, animal_quantity: int):

        self.update_current_active_feed_program(farmer_user_profile_id)

        if animal_quantity is None or animal_quantity <= 0:
            raise GlobalException(
                "Animal/flock quantity must be provided or available.",
                400
            )

        self.Client.table("feed_programs").insert({
            "farmer_user_profile_id": farmer_user_profile_id,
            "feed_product_id": feed_product_id,
            "animal_quantity": animal_quantity,
        }).execute()
        return None

    # Get active feed program (NOTE ONLY ONE ACTIVE PROGRAM IS ALLOWED)
    def get_active_feed_program(self, farmer_user_profile_id: int):
        response = (
            self.Client.table("feed_programs")
            .select("*")
            .eq("farmer_user_profile_id", farmer_user_profile_id)
            .eq("status", "active")
            .limit(1)
            .execute()
        )

        if not response.data or len(response.data) == 0:
            raise GlobalException(
                "There is no current active feed program.", 404)

        feed_program = response.data[0]

        updated_program = self._update_days_on_feed(feed_program)

        return updated_program

    def _update_days_on_feed(self, feed_program: dict) -> dict:
        try:
            start_date_str = feed_program.get("start_date")
            if not start_date_str:
                return feed_program

            start_date = parse(start_date_str)
            if start_date.tzinfo is None:
                start_date = start_date.replace(tzinfo=timezone.utc)

            now_utc = datetime.now(timezone.utc)
            time_diff = now_utc - start_date
            total_hours = time_diff.total_seconds() / 3600

            new_days_on_feed = int(total_hours // 24) + 1
            current_days_on_feed = feed_program.get("days_on_feed", 1)

            if new_days_on_feed != current_days_on_feed:
                update_response = (
                    self.Client.table("feed_programs")
                    .update({
                        "days_on_feed": new_days_on_feed,
                        "updated_at": now_utc.isoformat()
                    })
                    .eq("id", feed_program["id"])
                    .execute()
                )

                if update_response.data:
                    feed_program["days_on_feed"] = new_days_on_feed
                    feed_program["updated_at"] = now_utc.isoformat()
                    # print(f"Successfully updated days_on_feed from {current_days_on_feed} to {new_days_on_feed} for feed program {feed_program['id']}")
                else:
                    print(
                        f"Failed to update days_on_feed for feed program {feed_program['id']}")
            else:
                print(
                    f"No update needed. Days on feed is correct: {current_days_on_feed}")

            return feed_program

        except Exception as e:
            print(f"Error updating days_on_feed: {e}")
            import traceback
            traceback.print_exc()
            return feed_program

    # Update current active feed program (helper method when farmer switched midway without explicitly marking the current program as incomplete or complete)
    def update_current_active_feed_program(self, farmer_user_profile_id: int):
        response = (
            self.Client.table("feed_programs")
            .select("id")
            .eq("farmer_user_profile_id", farmer_user_profile_id)
            .eq("status", "active")
            .limit(1)
            .execute()
        )

        if response.data and len(response.data) > 0:
            active_id = response.data[0]["id"]
            self.Client.table("feed_programs").update({
                "status": "switched"
            }).eq("id", active_id).execute()

            return active_id

        return None

    def complete_active_feed_program(self, farmer_user_profile_id: int):
        response = (
            self.Client.table("feed_programs")
            .select("id")
            .eq("farmer_user_profile_id", farmer_user_profile_id)
            .eq("status", "active")
            .limit(1)
            .execute()
        )

        if response.data and len(response.data) > 0:
            active_id = response.data[0]["id"]
            self.Client.table("feed_programs").update({
                "status": "completed"
            }).eq("id", active_id).execute()
            return active_id

        return None

    def incomplete_active_feed_program(self, farmer_user_profile_id: int):
        response = (
            self.Client.table("feed_programs")
            .select("id")
            .eq("farmer_user_profile_id", farmer_user_profile_id)
            .eq("status", "active")
            .limit(1)
            .execute()
        )

        if response.data and len(response.data) > 0:
            active_id = response.data[0]["id"]
            self.Client.table("feed_programs").update({
                "status": "incomplete"
            }).eq("id", active_id).execute()
            return active_id

        return None

    # DASHBOARD COMPONENT DATA SECTION

    # Method to get current feed product associated with active feed program
    def get_active_feed_product(self, farmer_user_profile_id: int):
        feed_program_response = (
            self.Client.table("feed_programs")
            .select("id, feed_product_id, days_on_feed, status")
            .eq("farmer_user_profile_id", farmer_user_profile_id)
            .eq("status", "active")
            .limit(1)
            .execute()
        )

        if not feed_program_response.data:
            return None  # No active feed program

        feed_program = feed_program_response.data[0]

        # Fetch feed product details
        feed_product_response = (
            self.Client.table("feed_products")
            .select("id, name, feed_stage, age_range_start, age_range_end, goal")
            .eq("id", feed_program["feed_product_id"])
            .limit(1)
            .execute()
        )

        if not feed_product_response.data:
            return None  # No feed product found

        feed_product = feed_product_response.data[0]

        # Build DTO
        feed_product_dto = {
            "feed_program_id": feed_program["id"],
            "feed_name": feed_product["name"],
            "status": feed_program["status"],
            "feed_stage": feed_product["feed_stage"],
            "age_range_start": feed_product["age_range_start"],
            "age_range_end": feed_product["age_range_end"],
            "feed_goal": feed_product["goal"],
            "days_on_feed": feed_program["days_on_feed"],
        }

        return feed_product_dto

    # FEED CALCULATOR

    def create_feed_calculation_log(self, payload: CreateFeedCalculatorPayload) -> Dict:
        response = self.Client.table(
            "feed_calculation_logs").insert(payload).execute()
        return response.data[0] if response.data else {}

    def read_feed_calculation_log(self, farmer_user_profile_id: int) -> FeedCalculatorDto:
        response = (
            self.Client.table("feed_calculation_logs")
            .select("*")
            .eq("user_profile_id", farmer_user_profile_id)
            .execute()
        )

        print(response)

        if not response.data or len(response.data) == 0:
            raise GlobalException(
                "There is no current calculation log program.", 404)

        data = response.data[0]
        feed_calculation_log = FeedCalculatorDto(
            id=data["id"],
            farmer_user_profile_id=data["user_profile_id"],
            number_of_animals=data["number_of_animals"],
            feed_frequency=data["feed_frequency"],
            bag_size_kg=data["bag_size_kg"],
            current_stock_bags=data["current_stock_bags"],
            bag_cost_php=data["bag_cost_php"],
            animal_type=data["animal_type"],
            feed_stage=data["feed_stage"],
            daily_consumption_kg=data["daily_consumption_kg"],
            bags_needed_per_week=data["bags_needed_per_week"],
            cost_per_week_php=data["cost_per_week_php"],
            reorder_point_days=data["reorder_point_days"],
            alert_level=data["alert_level"],
            weekly_consumption_kg=data["weekly_consumption_kg"],
            created_at=data["created_at"],
            updated_at=data["updated_at"]
        )

        return feed_calculation_log

    def update_feed_calculation_log(self, id: int, payload: UpdateFeedCalculatorPayload) -> Dict:
        # payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        print(payload)
        response = self.Client.table("feed_calculation_logs") \
            .update(payload) \
            .eq("user_profile_id", payload["user_profile_id"]) \
            .execute()

        return response.data[0] if response.data else {}

    def read_growth_performance(self, farmer_user_profile_id: int) -> Dict:
        try:
            user_exists = (self.Client.table("user_profiles")
                           .select("id")
                           .eq("id", farmer_user_profile_id)
                           .limit(1)
                           .execute())

            if not user_exists.data:
                raise GlobalException(
                    f"User profile ID {farmer_user_profile_id} does not exist", 404)

            # Get active feed program
            try:
                feed_program = self.get_active_feed_program(
                    farmer_user_profile_id)
                feed_program_start_date = feed_program.get("start_date")
                feed_program_end_date = feed_program.get("end_date")
                feed_product_id = feed_program.get("feed_product_id")
                # Get initial flock size from the active feed program
                initial_flock_size = feed_program.get("animal_quantity", 0)
            except:
                return self.__get_default_growth_performance()

            # get farm performance logs within the active feed program
            farm_performance_logs = []
            if feed_program_start_date:
                query = (
                    self.Client.table("farm_performance_logs")
                    .select("*")
                    .eq("user_profile_id", farmer_user_profile_id)
                    .gte("created_at", feed_program_start_date)
                    # Order by oldest first for tracking
                    .order("created_at", desc=False)
                )
                if feed_program_end_date:
                    query = query.lte("created_at", feed_program_end_date)

                farm_logs_response = query.execute()
                farm_performance_logs = farm_logs_response.data or []

            # get health incidents within the active feed program
            health_incidents = []
            if feed_program_start_date:
                query = (
                    self.Client.table("health_incidents")
                    .select("*")
                    .eq("farmer_user_profile_id", farmer_user_profile_id)
                    .gte("created_at", feed_program_start_date)
                    # Order by oldest first for tracking
                    .order("created_at", desc=False)
                )
                if feed_program_end_date:
                    query = query.lte("created_at", feed_program_end_date)

                health_incidents_response = query.execute()
                health_incidents = health_incidents_response.data or []

            if not farm_performance_logs and not health_incidents:
                return self.__get_default_growth_performance()

            # Calculate dynamic flock tracking from both sources
            flock_tracking = self.__calculate_dynamic_flock_size(
                initial_flock_size, farm_performance_logs, health_incidents)

            current_flock_size = flock_tracking["current_flock_size"]
            total_mortality = flock_tracking["total_mortality"]
            mortality_percentage = flock_tracking["mortality_percentage"]
            survival_rate = flock_tracking["survival_rate"]

            total_farm_performance_logs = len(farm_performance_logs)
            # Re-order for latest first after calculations
            farm_performance_logs_desc = sorted(farm_performance_logs,
                                                key=lambda x: x["created_at"], reverse=True)
            latest_farm_performance_log = farm_performance_logs_desc[0]

            # Get the growth rate
            growth_data = self.__calculate_growth_rate(farm_performance_logs)
            growth_rate = growth_data["growth_rate"]

            # performance calculation section
            try:
                total_weight_kg = round(
                    sum(float(log.get("average_weight_kg", 0.0)) for log in farm_performance_logs), 3)

                # fcr = float(latest_farm_performance_log.get("feed_convertion_ratio", 1.0))
                # if fcr > 0:
                #     performance_index = round(
                #         ((average_weight * survival_rate) / fcr) * 100, 2)
                # else:
                #     performance_index = 0.0
            except (ValueError, TypeError):
                # average_weight = 0.0
                total_weight_kg = 0.0
                # performance_index = 0.0

            actual_weight = float(
                latest_farm_performance_log.get("average_weight_kg", 0.0))

            # Get target weight based on current feed product
            target_weight = self.__get_target_weight_by_feed_product(
                feed_product_id)

            # Build growth chart data - only for current feed program period
            growth_chart_data = []
            if feed_program_start_date and farm_performance_logs:
                latest_per_day = {}
                for log in farm_performance_logs:
                    date_str = parse(log["created_at"]).date().isoformat()
                    latest_per_day[date_str] = log

                growth_chart_data = [
                    {
                        "date": date,
                        "actual_weight": float(log.get("average_weight_kg", 0.0)),
                        "target_weight": target_weight
                    }
                    for date, log in sorted(latest_per_day.items())
                ]

            # Build recent records - only for current feed program period
            recent_records = []
            if feed_program_start_date and farm_performance_logs_desc:
                for log in farm_performance_logs_desc:
                    log_date = parse(log["created_at"]).date()
                    recent_records.append({
                        "date": log_date.isoformat(),
                        "actual_weight": float(log.get("average_weight_kg", 0.0)),
                        "note": log.get("notes", "")
                    })

            return {
                "daily_average_growth_rate": growth_rate,
                "actual_weight": actual_weight,
                "target_weight": target_weight,
                "growth_chart_data": growth_chart_data,
                "performance_analytics": {
                    "total_logs": total_farm_performance_logs,
                    "total_weight_kg": total_weight_kg,
                    "mortality_count": total_mortality,
                    "mortality_percentage": mortality_percentage,
                    "initial_flock_size": initial_flock_size,  # Starting flock size
                    # Current flock size after mortalities
                    "current_flock_size": current_flock_size,
                    # "survival_rate": survival_rate,
                    # Breakdown by source
                    "mortality_breakdown": flock_tracking["mortality_breakdown"],
                    "recent_records": recent_records,
                }
            }

        except GlobalException:
            raise
        except Exception as e:
            raise GlobalException(
                f"Error fetching growth performance: {e}", 500)

    def read_feed_intake_behavior(self, farmer_user_profile_id: int):
        try:
            user_exists = (self.Client.table("user_profiles")
                           .select("id")
                           .eq("id", farmer_user_profile_id)
                           .limit(1)
                           .execute())

            if not user_exists.data:
                raise GlobalException(
                    f"User profile ID {farmer_user_profile_id} does not exist.")

            try:
                feed_program = self.get_active_feed_program(
                    farmer_user_profile_id)
                feed_program_start_date = feed_program.get("start_date")
                feed_program_end_date = feed_program.get("end_date")
                feed_product_id = feed_program.get("feed_product_id")
            except GlobalException:
                return self.__get_default_feed_intake_behavior()

            # get farm performance logs within the active feed program
            farm_performance_logs = []
            if feed_program_start_date:
                query = (
                    self.Client.table("farm_performance_logs")
                    .select("*")
                    .eq("user_profile_id", farmer_user_profile_id)
                    .gte("created_at", feed_program_start_date)
                    .order("created_at", desc=True)
                )
                if feed_program_end_date:
                    query = query.lte("created_at", feed_program_end_date)

                farm_logs_response = query.execute()
                farm_performance_logs = farm_logs_response.data or []

            # If no logs for this feed program, return defaults
            if not farm_performance_logs:
                return self.__get_default_feed_intake_behavior()

            # Feed intake analysis
            feed_intake_summary = {
                "eating_well": 0,
                "picky": 0,
                "not_eating": 0
            }
            total_feed_behavior_logs = 0

            recent_feed_records = []
            for log in farm_performance_logs:
                behavior = log.get("feed_intake_status")
                animals_count = log.get("animals_count", 0)

                if behavior in feed_intake_summary and animals_count > 0:
                    feed_intake_summary[behavior] += animals_count
                    total_feed_behavior_logs += 1

                log_date = parse(log["created_at"])
                recent_feed_records.append({
                    "date": log_date.isoformat(),
                    "feed_intake_status": behavior,
                    "feed_intake_kg": log.get("feed_intake_kg"),
                    "animals_count": animals_count  # Include animals count in records
                })

            # Calculate behavior score based on animals, not logs
            score_weights = {
                "eating_well": 1.0,
                "picky": 0.5,
                "not_eating": 0.0
            }

            behavior_score = 0.0
            total_animals_counted = sum(feed_intake_summary.values())

            if total_animals_counted > 0:
                weighted_score = sum(
                    feed_intake_summary[k] * score_weights[k] for k in feed_intake_summary)
                behavior_score = round(
                    (weighted_score / total_animals_counted) * 100, 2)

            dominant_status = max(
                feed_intake_summary, key=feed_intake_summary.get) if total_animals_counted > 0 else "no_data"
            
            total_records_count = len(farm_performance_logs)
            recent_record_date = farm_performance_logs[0]["created_at"] if farm_performance_logs else None

            return {
                "behavior_score": behavior_score,
                "behavior_status": dominant_status,
                "summary": feed_intake_summary,  # Now shows animal counts, not log counts
                "total_records_count": total_records_count,
                "recent_record_date": recent_record_date,
                "recent_feed_records": recent_feed_records,
                "total_animals_analyzed": total_animals_counted,  # New field for transparency
            }

        except GlobalException:
            raise  # Re-raise GlobalException (user not found, etc.)
        except Exception as e:
            raise GlobalException(
                f"Error fetching feed intake behavior: {e}", status_code=500)

    def read_health_watch(self, farmer_user_profile_id: int, filter_type: Optional[str] = None) -> Dict:
        try:
            user_exists = (self.Client.table("user_profiles")
                           .select("id")
                           .eq("id", farmer_user_profile_id)
                           .limit(1)
                           .execute())

            if not user_exists.data:
                raise GlobalException(
                    f"User profile ID {farmer_user_profile_id} does not exist.", status_code=404)

            try:
                feed_program = self.get_active_feed_program(
                    farmer_user_profile_id)
                feed_program_start_date = feed_program.get("start_date")
                feed_program_end_date = feed_program.get("end_date")
                feed_product_id = feed_program.get("feed_product_id")
            except GlobalException:
                return self.__get_default_health_watch()

            # Calculate filter date based on filter_type
            filter_start_date = None
            if filter_type == "daily":
                filter_start_date = datetime.now().replace(
                    hour=0, minute=0, second=0, microsecond=0).isoformat()
            elif filter_type == "weekly":
                # Get start of current week (Monday)
                today = datetime.now()
                days_since_monday = today.weekday()
                start_of_week = today - timedelta(days=days_since_monday)
                filter_start_date = start_of_week.replace(
                    hour=0, minute=0, second=0, microsecond=0).isoformat()

            # Get health incidents within the active feed program period and apply additional filter if specified
            health_incidents = []
            if feed_program_start_date:
                query = (self.Client.table("health_incidents")
                         .select("*")
                         .eq("farmer_user_profile_id", farmer_user_profile_id)
                         .gte("created_at", feed_program_start_date)
                         .order("created_at", desc=True))

                if feed_program_end_date:
                    query = query.lte("created_at", feed_program_end_date)

                # Apply additional date filter if specified
                if filter_start_date:
                    # Use the later of feed_program_start_date or filter_start_date
                    effective_start_date = max(
                        feed_program_start_date, filter_start_date)
                    query = query.gte("created_at", effective_start_date)

                incident_logs_response = query.execute()
                health_incidents = incident_logs_response.data or []

            # Get farm performance logs within the active feed program period and apply additional filter if specified
            farm_performance_logs = []
            if feed_program_start_date:
                query = (
                    self.Client.table("farm_performance_logs")
                    .select("*")
                    .eq("user_profile_id", farmer_user_profile_id)
                    .gte("created_at", feed_program_start_date)
                    .order("created_at", desc=True)
                )
                if feed_program_end_date:
                    query = query.lte("created_at", feed_program_end_date)

                # Apply additional date filter if specified
                if filter_start_date:
                    # Use the later of feed_program_start_date or filter_start_date
                    effective_start_date = max(
                        feed_program_start_date, filter_start_date)
                    query = query.gte("created_at", effective_start_date)

                farm_logs_response = query.execute()
                farm_performance_logs = farm_logs_response.data or []

            # If no incidents or performance logs for this feed program, return defaults
            if not health_incidents and not farm_performance_logs:
                return self.__get_default_health_watch()

            sick_count = 0
            mortality_count = 0
            notes_count = 0
            health_score = 100

            recent_issues = []

            # Process health incidents
            for incident in health_incidents:
                kind = incident.get("incident_type")
                affected = incident.get("affected_count", 0)
                has_note = bool(incident.get("symptoms")
                                or incident.get("suspected_cause"))

                if kind == "sickness":
                    sick_count += affected
                    health_score -= affected * 2
                elif kind == "mortality":
                    mortality_count += affected
                    health_score -= affected * 4
                if has_note:
                    notes_count += 1
                    health_score -= 1

                recent_issues.append({
                    "date": incident.get("incident_date"),
                    "incident_type": kind,
                    "affected_count": affected,
                    "symptoms": incident.get("symptoms"),
                    "suspected_cause": incident.get("suspected_cause"),
                    "requires_vet_visit": incident.get("requires_vet_visit"),
                    "feed_info": incident.get("feed_info"),
                    "actions_taken": incident.get("actions_taken"),
                })

            # Process farm performance logs for mortality data
            for log in farm_performance_logs:
                log_mortality = log.get("mortality_count", 0)
                if log_mortality > 0:
                    mortality_count += log_mortality
                    health_score -= log_mortality * 4  # Same penalty as health incident mortality

                    # Add to recent issues for visibility
                    recent_issues.append({
                        "date": log.get("created_at"),
                        "incident_type": "mortality",
                        "affected_count": log_mortality,
                        "symptoms": "Recorded in performance log",
                        "suspected_cause": log.get("notes", "Not specified"),
                        "requires_vet_visit": False,
                        "feed_info": None,
                        "actions_taken": None,
                    })

            # Sort recent issues by date (most recent first)
            recent_issues.sort(key=lambda x: parse(x["date"]), reverse=True)

            health_score = max(0, min(health_score, 100))

            return {
                "health_score": health_score,
                "issue_summary": {
                    "sick": sick_count,
                    "mortality": mortality_count,
                    "notes": notes_count
                },
                "recent_issues": recent_issues,
                "filter_applied": filter_type or "all"
            }

        except GlobalException:
            raise  # Re-raise GlobalException (user not found, etc.)
        except Exception as e:
            raise GlobalException(
                f"Error fetching health watch data: {e}", status_code=500)

    # HELPER METHODS SECTION -----------------------------------

    def __get_default_growth_performance(self) -> Dict:
        """Return default growth performance structure for new users or users without active feed program"""
        return {
            "daily_average_growth_rate": 0.0,
            "current_fcr": 0.0,
            "actual_weight": 0.0,
            "target_weight": 0.0,
            "growth_chart_data": [],
            "performance_analytics": {
                "total_logs": 0,
                "total_weight_kg": 0.0,
                "mortality_count": 0,
                "mortality_percentage": 0.0,
                "performance_index": 0.0,
                "recent_records": [],
            }
        }

    def __calculate_growth_rate(self, logs: List[Dict]) -> Dict:
        """Calculate growth rate from performance logs"""
        if len(logs) < 2:
            return {
                "growth_rate": 0.0,
                "raw_gain_kg": 0.0
            }

        first_log = logs[-1]  # Oldest log in the period
        last_log = logs[0]    # Most recent log in the period

        try:
            weight_start = float(first_log.get("average_weight_kg", 0.0))
            weight_end = float(last_log.get("average_weight_kg", 0.0))
            date_start = parse(first_log["created_at"])
            date_end = parse(last_log["created_at"])

            days = (date_end - date_start).days
            if days <= 0:
                return {
                    "growth_rate": 0.0,
                    "raw_gain_kg": 0.0
                }

            return {
                "growth_rate": round((weight_end - weight_start) / days, 3),
                "raw_gain_kg": round((weight_end - weight_start), 3)
            }
        except (ValueError, TypeError) as e:
            print(f"Error calculating growth rate: {e}")
            return {
                "growth_rate": 0.0,
                "raw_gain_kg": 0.0
            }

    def __get_default_feed_intake_behavior(self) -> Dict:
        """Return default feed intake behavior structure for new users or users without active feed program"""
        return {
            "behavior_score": None,
            "behavior_status": "no_data",
            "summary": {
                "eating_well": 0,
                "picky": 0,
                "not_eating": 0
            },
            "recent_feed_records": [],
            "total_animals_analyzed": 0,
            "has_data": False,
        }

    def __get_default_health_watch(self) -> Dict:
        """Return default health watch structure for new users or users without active feed program"""
        return {
            "health_score": 100,
            "issue_summary": {
                "sick": 0,
                "mortality": 0,
                "notes": 0
            },
            "recent_issues": []
        }

    # def __get_flock_size(self, farmer_user_profile_id: int) -> int:
    #     """Get flock size for the farmer"""
    #     try:
    #         # Get flock size
    #         flock_size_response = self.Client.table("farmer_livestock").select("quantity") \
    #             .eq("farmer_user_profile_id", farmer_user_profile_id).single().execute()

    #         if flock_size_response.data:
    #             return flock_size_response.data.get("quantity", 0)
    #     except Exception:
    #         pass

    #     return 0
    
    def __calculate_dynamic_flock_size(self, initial_flock_size: int, farm_performance_logs: List[Dict], health_incidents: List[Dict]) -> Dict:
        if initial_flock_size <= 0:
            return {
                "current_flock_size": initial_flock_size,
                "total_mortality": 0,
                "mortality_percentage": 0.0,
                "survival_rate": 1.0,
                "mortality_breakdown": {
                    "from_performance_logs": 0,
                    "from_health_incidents": 0
                }
            }

        current_flock_size = initial_flock_size
        mortality_from_performance_logs = 0
        mortality_from_health_incidents = 0

        # Combine and sort all mortality events chronologically
        mortality_events = []

        # Add mortality events from farm performance logs
        for log in farm_performance_logs:
            mortality_count = log.get("mortality_count", 0)
            if mortality_count > 0:
                mortality_events.append({
                    "date": log["created_at"],
                    "count": mortality_count,
                    "source": "performance_log",
                    "log": log
                })

        # Add mortality events from health incidents
        for incident in health_incidents:
            if incident.get("incident_type") == "mortality":
                affected_count = incident.get("affected_count", 0)
                if affected_count > 0:
                    mortality_events.append({
                        "date": incident["created_at"],
                        "count": affected_count,
                        "source": "health_incident",
                        "incident": incident
                    })

        # Sort all mortality events chronologically
        mortality_events.sort(key=lambda x: parse(x["date"]))

        # Process mortality events in chronological order
        for event in mortality_events:
            mortality_count = event["count"]
            current_flock_size = max(0, current_flock_size - mortality_count)
            
            if event["source"] == "performance_log":
                mortality_from_performance_logs += mortality_count
            else:
                mortality_from_health_incidents += mortality_count

        total_mortality = mortality_from_performance_logs + mortality_from_health_incidents

        # Calculate percentages based on initial flock size
        if initial_flock_size > 0:
            mortality_percentage = round(
                (total_mortality / initial_flock_size) * 100, 2)
            survival_rate = round((current_flock_size / initial_flock_size), 4)
        else:
            mortality_percentage = 0.0
            survival_rate = 1.0

        return {
            "current_flock_size": current_flock_size,
            "total_mortality": total_mortality,
            "mortality_percentage": mortality_percentage,
            "survival_rate": survival_rate,
            "mortality_breakdown": {
                "from_performance_logs": mortality_from_performance_logs,
                "from_health_incidents": mortality_from_health_incidents
            }
        }

    def __get_target_weight_by_feed_product(self, feed_product_id: Optional[int]) -> float:
        """Get target weight based on feed product ID"""
        if not feed_product_id:
            return 0.0

        try:
            target_weight_response = self.Client.table("feed_growth_targets").select("target_weight_kg") \
                .eq("feed_product_id", feed_product_id).limit(1).single().execute()

            if target_weight_response.data:
                return float(target_weight_response.data["target_weight_kg"])
        except Exception:
            pass

        return 0.0


def create_health_incident_with_program(farmer_instance: FarmerV2, user_id: int, company_id: int, form_data: dict, parsed: dict) -> bool:
    """Create health incident linked to active feed program"""
    try:
        # Create health incident - association with feed program is handled
        # by date range logic in FarmerV2 read methods
        farmer_instance.Client.table("health_incidents").insert({
            "farmer_user_profile_id": user_id,
            "incident_date": form_data.get("incident_date"),
            "incident_type": form_data.get("incident_type"),
            "affected_count": form_data.get("affected_count"),
            "symptoms": form_data.get("symptoms"),
            "suspected_cause": form_data.get("suspected_cause"),
            "requires_vet_visit": form_data.get("requires_vet_visit"),
            "reported_by": user_id,
            "actions_taken": form_data.get("actions_taken"),
            "feed_info": form_data.get("feed_info"),
            "reported_by": user_id,
        }).execute()

        return True

    except Exception as e:
        print(f"Error creating health incident: {e}")
        return False


def create_performance_log_with_program(farmer_instance: FarmerV2, user_id: int, company_id: int, form_data: dict, parsed: dict) -> bool:
    """Create performance log linked to active feed program"""
    try:
        # Create performance log - association with feed program is handled
        # by date range logic in FarmerV2 read methods
        farmer_instance.Client.table("farm_performance_logs").insert({
            "company_id": company_id,
            "user_profile_id": user_id,
            "average_weight_kg": form_data.get("average_weight_kg"),
            "feed_conversion_ratio": form_data.get("feed_conversion_ratio"),
            "mortality_count": form_data.get("mortality_count"),
            "eggs_per_day": form_data.get("eggs_per_day"),
            "shell_quality_issues": form_data.get("shell_quality_issues"),
            "feed_intake_status": form_data.get("feed_intake_status"),
            "health_status": form_data.get("health_status"),
            "notes": form_data.get("notes"),
            "feed_intake_kg": form_data.get("feed_intake_kg"),
            "bags_used": form_data.get("bags_used"),
            "animals_count": form_data.get("animals_count")
        }).execute()

        return True

    except Exception as e:
        print(f"Error creating performance log: {e}")
        return False
