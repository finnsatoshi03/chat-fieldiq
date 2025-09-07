from datetime import datetime, date
from typing import List, Optional, Dict
from config.config import get_supabase_client
from collections import defaultdict
from calendar import month_abbr

class SalesRep:
    def __init__(self):
        self.client = get_supabase_client()
   
    def create_field_product_incident(self, reported_by: int, form_data: Dict, tag: str):
        self.client.table("field_product_incidents").insert({            
            **form_data,
            "tag": tag,
            "reported_by": reported_by,
            "updated_at": "now()", }).execute()
        return None
    
    def create_dealer_incident(self, reported_by: int, form_data: Dict, tag: str):
        self.client.table("dealer_incidents").insert({            
            **form_data,
            "tag": tag, 
            "reported_by": reported_by,
            "updated_at": "now()", }).execute()
        return None
    
    def create_sales_report(self, reported_by: int, form_data: Dict):
        print(form_data)
        self.client.table("sales_reports").insert({            
            **form_data,            
            "reported_by": reported_by,
            "updated_at": "now()", }).execute()
        return None
    
    def create_visit_report(self, reported_by: int, form_data: Dict):
        self.client.table("visit_reports").insert({            
            **form_data,            
            "reported_by": reported_by,
            "updated_at": "now()", }).execute()
        return None
    
    def update_visit_report(self, ticket_number: str, reported_by: int, form_data: Dict):
        (
            self.client
            .table("visit_reports")
            .update({
                **form_data,
                "updated_at": "now()",
            })
            .eq("reported_by", reported_by)
            .eq("ticket_number", ticket_number)
            .execute()
        )
        return None
    

    def get_monthly_sales(self, user_id: int) -> Dict[str, float]:
        response = (
            self.client
            .table("sales_reports")
            .select("*")
            .eq("reported_by", user_id)
            .execute()
        )
        data = response.data

        monthly_sales = defaultdict(float)
        total_sales = 0.0

        for row in data:
            sales_date_str = row.get("sale_date")
            if not sales_date_str:
                continue
            
            sales_date = datetime.fromisoformat(sales_date_str.replace("Z", "+00:00"))
            month_number = sales_date.month
            total = float(row.get("total") or 0.0)

            monthly_sales[month_number] += total
            total_sales += total

        result = []
        for month_num in sorted(monthly_sales):
            result.append({
                "month": month_abbr[month_num],  
                "volumeInfluenced": 14500,           
                "closedSales": monthly_sales[month_num]
            })
        month_count = len(monthly_sales)
        avg_sales = total_sales / month_count if month_count else 0.0

        response = (
            self.client
            .table("sales_reps")
            .select("territory")
            .eq("user_profile_id", user_id)
            .execute()
        )

        data = response.data

        # Extract the region (territory)
        region = data[0]["territory"] if data else None

        # Map Philippine regions to Luzon / Visayas / Mindanao
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

        continent = region_to_island_group.get(region, "Unknown")

        return {
            "monthly_sales": result,
            "average_sales": avg_sales,
            "region": region,
            "continent": continent
        }

    def get_farms(self, user_id: int) -> Dict[str, object]:
        response = (
            self.client
            .table("visit_reports")
            .select("farm_name, location, visit_date, visit_type, notes, purpose, ticket_number")
            .eq("reported_by", user_id)
            .execute()
        )
        data = response.data

        farm_data = []
        planned_count = 0
        completed_count = 0

        for row in data:
            raw_date = row.get("visit_date")
            visit_type = row.get("visit_type")

            if raw_date:
                dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                formatted_date = dt.strftime("%b %d, %Y")   
                formatted_time = dt.strftime("%I:%M %p").lstrip("0")
            else:
                formatted_date = None
                formatted_time = None

            farm_data.append({
                "farm_name": row.get("farm_name"),
                "location": row.get("location"),
                "visit_type": visit_type,
                "visit_date": formatted_date,
                "visit_time": formatted_time
            })

            if visit_type == "planned_visit":
                planned_count += 1
            elif visit_type == "completed_visit":
                completed_count += 1

        return {
            "farms": farm_data,
            "planned_count": planned_count,
            "completed_count": completed_count
        }
    
    def get_visits(self, user_id: int) -> List[Dict]:
        response = (
            self.client
            .table("visit_reports")
            .select("id, ticket_number, farm_name, location, visit_type, visit_date, purpose, observations, notes")
            .eq("reported_by", user_id)
            .execute()
        )
        data = response.data or []

        status_map = {
            "planned_visit": "scheduled",
            "completed_visit": "completed",
            "overdue": "overdue"
        }

        visits = []

        for row in data:
            visit_type = row.get("visit_type")
            visit_date_str = row.get("visit_date")

            if not visit_date_str:
                continue

            # Parse and format date
            visit_dt = datetime.fromisoformat(visit_date_str.replace("Z", "+00:00"))

            visit_entry = {
                "id": row.get("id"),
                "farmName": row.get("farm_name"),
                "ticket_number": row.get("ticket_number"),
                "location": row.get("location"),
                "status": status_map.get(visit_type, "overdue"),
                "scheduledDate": visit_dt.isoformat(),
                "notes": row.get("purpose"),
                "observations": row.get("observations"),
                "notes1": row.get("notes"),
                "contactPerson": "Juan dela Cruz",
                "phoneNumber": "+63 917 123 4567",
                "priority": "high",
                "gpsCoordinates": {
                    "lat": 14.1693,
                    "lng": 121.2416
                },
                "type": "visit"
            }

            visits.append(visit_entry)

        return visits

    def get_alert_incidents(self, user_id: int) -> Dict[str, List[Dict]]:
        def fetch_tagged_data(table: str, tag: str):
            response = (
                self.client
                .table(table)
                .select("id", "problem", "description, created_at")
                .eq("reported_by", user_id)
                .execute()
            )
            data = getattr(response, "data", []) or []
            level = "warning"
            if tag == "product quality" or tag == "stock":
                level = "high"
            if tag == "pricing" or tag == "others":
                level = "medium"
                            
            return [
            {
                "id": item.get("id", ""),
                "type": tag,
                "level": level,
                "title": item.get("problem") or "New Sales",
                "description": item.get("description", ""),
                "timestamp": item.get("created_at", ""),
                
            }
            for item in data
        ]

        field_data = fetch_tagged_data("field_product_incidents", "warning")
        dealer_data = fetch_tagged_data("dealer_incidents", "warning")
        sales_data = fetch_tagged_data("sales_reports", "success")
        
        all_data = field_data + dealer_data + sales_data

        return {"data": all_data}
    
    def check_ticket_number_validity(self, ticket_number: str, user_id: int) -> bool:
        response = (
            self.client
            .table("visit_reports")
            .select("ticket_number")
            .eq("reported_by", user_id)
            .eq("ticket_number", ticket_number)
            .execute()
        )

        return bool(response.data)

    def generate_ticket_number(self, user_id: int) -> str:
        response = (
            self.client
            .table("visit_reports")
            .select("ticket_number", count="exact")
            .eq("reported_by", user_id)
            .execute()
        )

        count = (response.count or 0) + 1

        ticket_number = f"TKT-0000{user_id}-{count}"

        return ticket_number
