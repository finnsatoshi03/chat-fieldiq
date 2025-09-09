from datetime import date, datetime
from typing import List, Optional, Dict
from config.config import get_supabase_client
from collections import defaultdict
import json
import random

from exceptions.global_exception import GlobalException


class Admin:
    def __init__(self):
        self.client = get_supabase_client()


    def get_sales_data(self, company_id: int) -> List[Dict[str, object]]:
        # Fetch users + their sales_rep info in one query
        user_profiles_response = (
            self.client
            .table("user_profiles")
            .select("id, first_name, last_name, sales_reps(territory, quota_monthly)")
            .eq("company_id", company_id)
            .execute()
        )

        users = user_profiles_response.data or []
        if not users:
            return []

        # Map Philippine regions → island groups
        region_to_island_group = {
            # Luzon
            "Ilocos Region": "Luzon",
            "Cagayan Valley": "Luzon",
            "Central Luzon": "Luzon",
            "CALABARZON": "Luzon",
            "MIMAROPA": "Luzon",
            "Bicol Region": "Luzon",
            "NCR": "Luzon",
            "CAR": "Luzon",

            # Visayas
            "Western Visayas": "Visayas",
            "Central Visayas": "Visayas",
            "Eastern Visayas": "Visayas",

            # Mindanao
            "Zamboanga Peninsula": "Mindanao",
            "Northern Mindanao": "Mindanao",
            "Davao Region": "Mindanao",
            "SOCCSKSARGEN": "Mindanao",
            "Caraga": "Mindanao",
            "BARMM": "Mindanao",
        }

        # Collect user_ids
        user_ids = [u["id"] for u in users]

        # Fetch sales reports
        sales_response = (
            self.client
            .table("sales_reports")
            .select("reported_by, total")
            .in_("reported_by", user_ids)
            .execute()
        )
        sales_data = sales_response.data or []

        # Aggregate sales per user
        sales_by_user = defaultdict(float)
        for row in sales_data:
            user_id = row["reported_by"]
            sales_by_user[user_id] += float(row.get("total") or 0.0)
            
        # Final assembly
        result = []
        for u in users:
            user_id = u["id"]
            # Handle null names gracefully
            first_name = u.get("first_name") or ""
            last_name = u.get("last_name") or ""
            name = (first_name + " " + last_name).strip() or f"User {user_id}"

            # Handle sales_reps as a list
            sales_rep_list = u.get("sales_reps") or []
            sales_rep = sales_rep_list[0] if sales_rep_list else {}

            region = sales_rep.get("territory", "") if sales_rep else ""
            quota = sales_rep.get("quota_monthly", 0.0) if sales_rep else 0.0
            continent = region_to_island_group.get(region, "Unknown")

            closed_sales = sales_by_user.get(user_id, 0.0)
            growth_rate = (closed_sales / quota * 100) if quota else 0.0

            result.append({
                "id": str(user_id),
                "region": region,
                "continent": continent,      # Luzon / Visayas / Mindanao
                "rep": name,
                "targetInfluence": quota,
                "closedSales": closed_sales,
                "growthRate": growth_rate,
                "period": "2024-Q4"
            })

        return result

    def get_farms(self, company_id: int) -> List[Dict[str, object]]:
        
        company_farmers = (
            self.client
            .table("company_farmers")
            .select(
                "company_id,"
                "farmer:user_profiles!company_farmers_farmer_user_profile_id_fkey("
                    "id, first_name, last_name, "
                    "farmer_details:farmers!farmers_user_profile_id_fkey(*)"
                "), "
                "salesrep:user_profiles!company_farmers_assigned_sales_rep_user_profile_id_fkey("
                    "id, first_name, last_name, "
                    "salesrep_details:sales_reps!sales_reps_user_profile_id_fkey(*)"
                ")"
            )            
            .eq("company_id", company_id)
            .execute()
        )

        # Track counts as we loop
        salesrep_counts = defaultdict(int)

        for row in company_farmers.data:
            salesrep = row.get("salesrep", {})
            rep_id = salesrep.get("id")

            if rep_id:
                salesrep_counts[rep_id] += 1
                # Add total count to current row's salesrep
                salesrep["count"] = salesrep_counts[rep_id]
            else:
                # In case of missing salesrep or ID
                salesrep["count"] = 0
                row["salesrep"] = salesrep
        
              
        return company_farmers.data

    def get_dealers_issue(self, company_id: int) -> List[Dict[str, object]]:
        priority_levels = ["low", "medium", "high", "critical"]

        user_profiles_response = (
            self.client
            .table("user_profiles")
            .select("id, first_name, last_name")
            .eq("company_id", company_id)
            .execute()
        )

        users = user_profiles_response.data or []
        user_id_map = {
            u["id"]: {
                "full_name": f"{u.get('first_name', '')} {u.get('last_name', '')}".strip(),               
            }
            for u in users
        }

        user_ids = list(user_id_map.keys())
        if not user_ids:
            return []

        dealer_issues_response = (
            self.client
            .table("dealer_incidents")
            .select("*")
            .in_("reported_by", user_ids)
            .execute()
        )

        incidents = dealer_issues_response.data or []

        grouped_data = defaultdict(list)
        for incident in incidents:
            grouped_data[incident["reported_by"]].append(incident)

        result = []
        for user_id, issues in grouped_data.items():
            profile = user_id_map.get(user_id, {})
            formatted_issues = []

            for issue in issues:
                formatted_issues.append({
                    "type": issue.get("problem", "Unknown"),
                    "description": issue.get("description", ""),
                    "reportedDate": issue.get("created_at", "")[:10],
                    "status": "open",
                    "priority": random.choice(priority_levels)
                })

            result.append({
                "id": user_id,
                "dealerName": profile.get("full_name", f"Dealer {user_id}"),
                "dealerCode": f"DEALER-{str(user_id).zfill(4)}",
                "location": {
                    "lat": 0,
                    "lng": 0,
                    "address": issue.get("location", ""),
                    "region": ""
                },
                "issues": formatted_issues,
                "severity": random.choice(priority_levels),
                "lastUpdated": issues[0].get("updated_at"),
                "contactPerson": "N/A",
                "phone": "N/A",
                "email": "N/A"
            })
            
        return result

    def get_farm_performance(self, company_id: int) -> Dict[str, object]:
        response = (
            self.client
            .table("farm_performance_logs")
            .select("""
                id,
                company_id,
                user_profile_id,
                average_weight_kg,
                feed_conversion_ratio,
                mortality_count,
                eggs_per_day,
                feed_intake_kg,
                bags_used,
                created_at,
                updated_at,
                user_profiles (
                    id,
                    farmers (
                        farm_name,
                        farm_type,
                        location_province,
                        location_city,
                        location_barangay,
                        longitude,
                        latitude,
                        days_on_feed,
                        current_feed
                    )
                )
            """)
            .eq("company_id", company_id)
            .execute()
        )

        data = response.data or []

        metrics = []
        region_map = {}
        timeline_map = {}

        for row in data:
            user_profile = row.get("user_profiles", {})
            farmers  = user_profile.get("farmers", {})
            # farm = row.get("farm", {})
            created_at = row["created_at"][:10]

            for farm in farmers:
                metric = {
                    "id": row["id"],
                    "productId": farm.get("current_feed"),
                    "productName": farm.get("current_feed"),
                    "farmId": row["user_profile_id"],
                    "farmName": farm.get("farm_name"),
                    "region": farm.get("location_province"),
                    "province": farm.get("location_province"),
                    "gpsCoordinates": {
                        "lat": farm.get("latitude"),
                        "lng": farm.get("longitude")
                    },
                    "recordDate": created_at,
                    "batchSize": None,
                    "daysOnFeed": farm.get("days_on_feed"),
                    "fcr": row.get("feed_conversion_ratio"),
                    "weightGain": None,
                    "mortality": row.get("mortality_count"),
                    "avgWeight": row.get("average_weight_kg"),
                    "feedIntake": row.get("feed_intake_kg"),
                    "weatherCondition": "moderate",
                    "managementScore": random.randint(6, 9),
                    "reportedBy": "Unknown Vet",
                    "verified": True
                }
                metrics.append(metric)

            # Regional aggregation
            region = farm.get("location_province")
            if region:
                if region not in region_map:
                    region_map[region] = {
                        "region": region,
                        "province": region,
                        "gpsCoordinates": {
                            "lat": farm.get("latitude"),
                            "lng": farm.get("longitude")
                        },
                        "totalFarms": 0,
                        "fcrs": [],
                        "weightGains": [],
                        "mortalities": [],
                        "topProduct": farm.get("current_feed"),
                        "performanceRating": "good",
                        "lastUpdate": created_at
                    }

                region_map[region]["totalFarms"] += 1
                if row.get("feed_conversion_ratio"):
                    region_map[region]["fcrs"].append(row["feed_conversion_ratio"])
                if row.get("average_weight_kg"):
                    region_map[region]["weightGains"].append(row["average_weight_kg"])
                if row.get("mortality_count"):
                    region_map[region]["mortalities"].append(row["mortality_count"])
                if created_at > region_map[region]["lastUpdate"]:
                    region_map[region]["lastUpdate"] = created_at

            # Timeline aggregation
            if created_at not in timeline_map:
                timeline_map[created_at] = {
                    "fcrs": [],
                    "weightGains": [],
                    "mortalities": [],
                    "feedIntakes": [],
                    "managementScores": []
                }

            if row.get("feed_conversion_ratio"):
                timeline_map[created_at]["fcrs"].append(row["feed_conversion_ratio"])
            if row.get("average_weight_kg"):
                timeline_map[created_at]["weightGains"].append(row["average_weight_kg"])
            if row.get("mortality_count"):
                timeline_map[created_at]["mortalities"].append(row["mortality_count"])
            if row.get("feed_intake_kg"):
                timeline_map[created_at]["feedIntakes"].append(row["feed_intake_kg"])
            timeline_map[created_at]["managementScores"].append(random.randint(6, 9))

        # Build regional summary
        regional = []
        for region_data in region_map.values():
            regional.append({
                "region": region_data["region"],
                "province": region_data["province"],
                "gpsCoordinates": region_data["gpsCoordinates"],
                "totalFarms": region_data["totalFarms"],
                "avgFcr": round(sum(region_data["fcrs"]) / len(region_data["fcrs"]), 2) if region_data["fcrs"] else None,
                "avgWeightGain": round(sum(region_data["weightGains"]) / len(region_data["weightGains"]), 2) if region_data["weightGains"] else None,
                "avgMortality": round(sum(region_data["mortalities"]) / len(region_data["mortalities"]), 2) if region_data["mortalities"] else None,
                "topProduct": region_data["topProduct"],
                "performanceRating": region_data["performanceRating"],
                "lastUpdate": region_data["lastUpdate"]
            })

        # Build timeline
        timeline = []
        for date, val in sorted(timeline_map.items()):
            timeline.append({
                "date": date,
                "fcr": round(sum(val["fcrs"]) / len(val["fcrs"]), 2) if val["fcrs"] else None,
                "weightGain": round(sum(val["weightGains"]) / len(val["weightGains"]), 2) if val["weightGains"] else None,
                "mortality": round(sum(val["mortalities"]) / len(val["mortalities"]), 2) if val["mortalities"] else None,
                "feedIntake": round(sum(val["feedIntakes"]) / len(val["feedIntakes"]), 2) if val["feedIntakes"] else None,
                "managementScore": round(sum(val["managementScores"]) / len(val["managementScores"]), 2)
            })

        return {
            "metrics": metrics,
            "regional": regional,
            "timeline": timeline
        }

    def get_faqs(self, company_id: int) -> Dict[str, object]:
        response = (
            self.client
            .table("faq")
            .select("*")
            .eq("company_id", company_id)
            .order("created_at", desc=True)
            .execute()
        )

        data = response.data or []

        faqs = []
        category_counter = {}

        for item in data:
            category = item.get("category", "General")

            # Track how many times each category appears
            category_counter[category] = category_counter.get(category, 0) + 1

            faq = {
                "id": item["id"],
                "question": item["question"],
                "answer": item["answer"],
                "category": category,
                "status": "active",
                "priority": random.randint(1, 4),
                "views": random.randint(500, 5000),
                "lastUpdated": item["created_at"],
                "createdBy": "Chat AI Assistant",
                "tags": [category.lower()]  # You can add more if you want
            }
            faqs.append(faq)

        # Optionally, sort FAQs by most common category (top shown first)
        faqs.sort(key=lambda x: category_counter.get(x["category"], 0), reverse=True)

        return faqs

    def create_faq(self, question: str, answer: str, category: str, is_featured: bool = False) -> Dict:
        payload = {
            "question": question,
            "answer": answer,
            "category": category,
            "is_featured": is_featured,
        }

        response = (
            self.client
            .table("faq")
            .insert(payload)
            .execute()
        )

        return response.data[0] if response.data else {}

    def update_faq(self, faq_id: int, updates: Dict[str, object]) -> Dict:
        response = (
            self.client
            .table("faq")
            .update(updates)
            .eq("id", faq_id)
            .execute()
        )

        return response.data[0] if response.data else {}

    def delete_faq(self, faq_id: int) -> bool:
        response = (
            self.client
            .table("faq")
            .delete()
            .eq("id", faq_id)
            .execute()
        )

        return response.status_code == 200

    # SALES GOAL RELATED METHODS

    def get_sales_goals(self, company_id: int) -> List[Dict[str, object]]:
        response = self.client.table("sales_goals") \
            .select("*") \
            .eq("company_id", company_id) \
            .order("period_start", desc=True) \
            .execute()

        rows = response.data or []
        today = date.today()

        for row in rows:
            # Convert ISO strings from database to date objects for comparison
            period_end = datetime.fromisoformat(row["period_end"]).date()
            period_start = datetime.fromisoformat(row["period_start"]).date()

            if today > period_end:
                row["status"] = "past"
            elif today < period_start:
                row["status"] = "future"
            else:
                row["status"] = "active"

        return rows

    def create_sales_goal(self, company_id: int, target_amount: float, period_start: date, period_end: date, created_by: int) -> Dict:

        existing = self.client.table("sales_goals") \
            .select("*") \
            .eq("company_id", company_id) \
            .eq("period_start", period_start.isoformat()) \
            .eq("period_end", period_end.isoformat()) \
            .execute()

        if existing.data:
            raise GlobalException(
                "Sales goal for this period already exists. Please update instead.", 401)

        payload = {
            "company_id": company_id,
            "target_amount": target_amount,
            # Convert date objects to ISO string format for JSON serialization
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "created_by": created_by,
        }

        response = self.client.table("sales_goals") \
            .insert(payload) \
            .execute()

        return response.data[0] if response.data else {}

    def update_sales_goal(self, goal_id: int, updates: Dict[str, object]) -> Dict:
        # First fetch
        existing = (
            self.client
            .table("sales_goals")
            .select("*")
            .eq("id", goal_id)
            .single()
            .execute()
        )
        goal = existing.data
        if not goal:
            raise ValueError("Sales goal not found.")

        # Check editability
        today = date.today()
        # Fix: Convert ISO string from database back to date object
        start_date = datetime.fromisoformat(goal["period_start"]).date() if isinstance(
            goal["period_start"], str) else goal["period_start"]
        end_date = datetime.fromisoformat(goal["period_end"]).date() if isinstance(
            goal["period_end"], str) else goal["period_end"]

        if end_date < today:  # past goal
            raise PermissionError(
                "Past sales goals are locked and cannot be updated.")

        # Update allowed
        response = (
            self.client
            .table("sales_goals")
            .update(updates)
            .eq("id", goal_id)
            .execute()
        )
        return response.data[0] if response.data else {}

    def get_current_sales_goal(self, company_id: int) -> Optional[Dict[str, object]]:
        today = date.today().isoformat()  # Convert to ISO string for database query
        response = (
            self.client
            .table("sales_goals")
            .select("*")
            .eq("company_id", company_id)
            .lte("period_start", today)
            .gte("period_end", today)
            .single()
            .execute()
        )
        return response.data
