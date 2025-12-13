from http.server import BaseHTTPRequestHandler
import json
import os
import psycopg2
from datetime import datetime

# Helper to handle CORS (Cross-Origin Resource Sharing)
# This ensures your Lovable frontend can actually talk to this backend.
def set_cors_headers(handler):
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
    handler.send_header('Access-Control-Allow-Headers', 'Content-Type')

class handler(BaseHTTPRequestHandler):
    
    # Handle pre-flight requests (browsers check this before sending data)
    def do_OPTIONS(self):
        self.send_response(200)
        set_cors_headers(self)
        self.end_headers()

    def do_POST(self):
        try:
            # 1. Parse the Request Body
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            # Extract inputs
            reactor_type = data.get('reactorType', 'Unknown')
            enrichment = float(data.get('enrichment', 5.0))
            pressure = float(data.get('pressure', 15.5))
            years = int(data.get('years', 60))

            # 2. RUN THE PHYSICS SIMULATION (Python Logic)
            simulation_results = []
            
            for t in range(years + 1):
                # Linear degradation: 0% at year 0, 100% at year 60
                degradation = (t / 60.0) * 100.0
                
                # Fuel Burnup Model:
                # Starts at enrichment level, depletes to 0 around year 50
                fuel_state = max(0, enrichment - (enrichment * (t / 50.0)))
                
                # Reactor "Poison" (Xenon/Samarium)
                # Simulating a build-up that stabilizes, then spikes if cooling fails
                poison_ppm = (t * 25) + 100
                
                # Thermal Efficiency
                # Drops as components degrade
                efficiency = max(0, 35.0 - (t * 0.25))

                simulation_results.append({
                    "year": t,
                    "fuelState": round(fuel_state, 3),
                    "degradation": round(degradation, 1),
                    "poison": int(poison_ppm),
                    "efficiency": round(efficiency, 2)
                })

            # 3. SAVE TO NEON DATABASE
            # We connect, insert, and close quickly.
            conn = psycopg2.connect(os.environ["DATABASE_URL"])
            cursor = conn.cursor()
            
            insert_query = """
                INSERT INTO simulation_runs (reactor_type, inputs, results, created_at)
                VALUES (%s, %s, %s, NOW())
                RETURNING id;
            """
            
            # Serialize dicts to JSON for storage
            cursor.execute(insert_query, (
                reactor_type, 
                json.dumps(data), 
                json.dumps(simulation_results)
            ))
            
            run_id = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
            conn.close()

            # 4. Return Success Response
            self.send_response(200)
            set_cors_headers(self)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            response = {
                "success": True, 
                "runId": run_id, 
                "data": simulation_results
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))

        except Exception as e:
            # Handle Errors Gracefully
            self.send_response(500)
            set_cors_headers(self)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
