from http.server import BaseHTTPRequestHandler
import json
import os
import psycopg2

# CORS Helper (Same as before)
def set_cors_headers(handler):
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
    handler.send_header('Access-Control-Allow-Headers', 'Content-Type')

class handler(BaseHTTPRequestHandler):
    
    def do_OPTIONS(self):
        self.send_response(200)
        set_cors_headers(self)
        self.end_headers()

    def do_GET(self):
        try:
            # 1. Connect to Neon
            conn = psycopg2.connect(os.environ["DATABASE_URL"])
            cursor = conn.cursor()

            # 2. Query all presets
            # We order by category so the frontend can easily group them (Fission vs Fusion)
            query = """
                SELECT 
                    id, name, category, description,
                    default_fuel_type, default_enrichment, default_pressure, 
                    default_temp, default_flow_rate, default_pins,
                    limit_efficiency, limit_capacity_factor, limit_power_mw, limit_temp_material
                FROM reactor_presets
                ORDER BY category DESC, name ASC;
            """
            cursor.execute(query)
            
            # 3. Format as JSON
            # This magic line converts the database rows (tuples) into a list of dictionaries
            # using the column names from the database query.
            columns = [desc[0] for desc in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]

            cursor.close()
            conn.close()

            # 4. Return Response
            self.send_response(200)
            set_cors_headers(self)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            # Send the list directly
            self.wfile.write(json.dumps(results).encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            set_cors_headers(self)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
