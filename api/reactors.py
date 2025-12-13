from http.server import BaseHTTPRequestHandler
import json
import os
import psycopg2

# CORS Helper
def set_cors_headers(handler):
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
    handler.send_header('Access-Control-Allow-Headers', 'Content-Type')

class handler(BaseHTTPRequestHandler):
    
    def do_OPTIONS(self):
        self.send_response(200)
        set_cors_headers(self)
        self.end_headers()

    def do_GET(self):
        try:
            # 1. Connect to Neon
            conn = psycopg2.connect(os.environ["POSTGRES_URL"])
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

    def do_POST(self):
        """Create a new reactor preset"""
        try:
            # 1. Parse the Request Body
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            # 2. Validate required fields
            required_fields = ['name', 'category', 'description']
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Missing required field: {field}")

            # 3. Connect to database
            conn = psycopg2.connect(os.environ["POSTGRES_URL"])
            cursor = conn.cursor()

            # 4. Insert new preset
            insert_query = """
                INSERT INTO reactor_presets (
                    name, category, description,
                    default_fuel_type, default_enrichment, default_pressure,
                    default_temp, default_flow_rate, default_pins,
                    limit_efficiency, limit_capacity_factor, limit_power_mw, limit_temp_material
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, name, category, description,
                    default_fuel_type, default_enrichment, default_pressure,
                    default_temp, default_flow_rate, default_pins,
                    limit_efficiency, limit_capacity_factor, limit_power_mw, limit_temp_material;
            """

            cursor.execute(insert_query, (
                data.get('name'),
                data.get('category'),
                data.get('description'),
                data.get('default_fuel_type'),
                data.get('default_enrichment'),
                data.get('default_pressure'),
                data.get('default_temp'),
                data.get('default_flow_rate'),
                data.get('default_pins'),
                data.get('limit_efficiency'),
                data.get('limit_capacity_factor'),
                data.get('limit_power_mw'),
                data.get('limit_temp_material')
            ))

            # 5. Get the created preset
            columns = [desc[0] for desc in cursor.description]
            result = dict(zip(columns, cursor.fetchone()))

            conn.commit()
            cursor.close()
            conn.close()

            # 6. Return success response
            self.send_response(201)
            set_cors_headers(self)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode('utf-8'))

        except ValueError as e:
            self.send_response(400)
            set_cors_headers(self)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
        except Exception as e:
            self.send_response(500)
            set_cors_headers(self)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

    def do_PUT(self):
        """Update an existing reactor preset"""
        try:
            # 1. Parse the Request Body
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            # 2. Validate ID is provided
            if 'id' not in data:
                raise ValueError("Missing required field: id")

            preset_id = data.get('id')

            # 3. Connect to database
            conn = psycopg2.connect(os.environ["POSTGRES_URL"])
            cursor = conn.cursor()

            # 4. Build dynamic update query based on provided fields
            update_fields = []
            update_values = []

            allowed_fields = [
                'name', 'category', 'description',
                'default_fuel_type', 'default_enrichment', 'default_pressure',
                'default_temp', 'default_flow_rate', 'default_pins',
                'limit_efficiency', 'limit_capacity_factor', 'limit_power_mw', 'limit_temp_material'
            ]

            for field in allowed_fields:
                if field in data:
                    update_fields.append(f"{field} = %s")
                    update_values.append(data[field])

            if not update_fields:
                raise ValueError("No fields to update")

            # Add the ID to the end of values list
            update_values.append(preset_id)

            update_query = f"""
                UPDATE reactor_presets
                SET {', '.join(update_fields)}
                WHERE id = %s
                RETURNING id, name, category, description,
                    default_fuel_type, default_enrichment, default_pressure,
                    default_temp, default_flow_rate, default_pins,
                    limit_efficiency, limit_capacity_factor, limit_power_mw, limit_temp_material;
            """

            cursor.execute(update_query, update_values)

            # 5. Get the updated preset
            row = cursor.fetchone()
            if row is None:
                raise ValueError(f"Preset with id {preset_id} not found")

            columns = [desc[0] for desc in cursor.description]
            result = dict(zip(columns, row))

            conn.commit()
            cursor.close()
            conn.close()

            # 6. Return success response
            self.send_response(200)
            set_cors_headers(self)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode('utf-8'))

        except ValueError as e:
            self.send_response(400)
            set_cors_headers(self)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
        except Exception as e:
            self.send_response(500)
            set_cors_headers(self)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

    def do_DELETE(self):
        """Delete a reactor preset"""
        try:
            # 1. Parse the Request Body
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            # 2. Validate ID is provided
            if 'id' not in data:
                raise ValueError("Missing required field: id")

            preset_id = data.get('id')

            # 3. Connect to database
            conn = psycopg2.connect(os.environ["POSTGRES_URL"])
            cursor = conn.cursor()

            # 4. Delete the preset
            delete_query = """
                DELETE FROM reactor_presets
                WHERE id = %s
                RETURNING id;
            """

            cursor.execute(delete_query, (preset_id,))

            # 5. Check if preset was found and deleted
            row = cursor.fetchone()
            if row is None:
                raise ValueError(f"Preset with id {preset_id} not found")

            conn.commit()
            cursor.close()
            conn.close()

            # 6. Return success response
            self.send_response(200)
            set_cors_headers(self)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "id": preset_id}).encode('utf-8'))

        except ValueError as e:
            self.send_response(400)
            set_cors_headers(self)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
        except Exception as e:
            self.send_response(500)
            set_cors_headers(self)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
