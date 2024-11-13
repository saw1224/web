from flask import Flask, render_template, request, redirect, url_for, jsonify
from pyzbar.pyzbar import decode
import cv2
import base64
import numpy as np
from datetime import datetime
import sqlite3
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection
def create_connection():
    try:
        conn = sqlite3.connect('carrosISI.db')
        return conn
    except sqlite3.Error as e:
        logger.error(f"Database connection error: {e}")
    return None

def create_tables(conn):
    try:
        cursor = conn.cursor()
        
        # Create CheckListAutos table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS CheckListAutos (
                numero_coche TEXT PRIMARY KEY,
                kilometraje INTEGER,
                estado_llantas TEXT,
                estado_rines TEXT,
                detalles_raspones TEXT,
                estado_faros TEXT,
                otros_detalles TEXT,
                ultima_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create RegistrosAutos table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS RegistrosAutos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                qr_code TEXT,
                nombre_tecnico TEXT,
                ultimo_mantenimiento TIMESTAMP,
                salida TIMESTAMP,
                regreso TIMESTAMP
            )
        ''')
        
        conn.commit()
        logger.info("Tables created successfully")
    except sqlite3.Error as e:
        logger.error(f"Error creating tables: {e}")

def init_db():
    conn = create_connection()
    if conn is not None:
        create_tables(conn)
        conn.close()
    else:
        logger.error("Error! Cannot create the database connection.")

# Initialize database
init_db()

def registrar_salida_regreso(qr_code, nombre_tecnico, ultimo_mantenimiento, accion):
    conn = create_connection()
    if conn is None:
        return False

    try:
        cursor = conn.cursor()

        try:
            ultimo_mantenimiento_dt = datetime.fromisoformat(ultimo_mantenimiento)
        except ValueError as e:
            logger.error(f"Formato de fecha incorrecto en 'ultimo_mantenimiento': {e}")
            return False

        logger.info(f"Registrando con QR code: {qr_code}, Acción: {accion}")

        query_select = "SELECT id, salida, regreso FROM RegistrosAutos WHERE qr_code = ?"
        cursor.execute(query_select, (qr_code,))
        registro_existente = cursor.fetchone()

        if registro_existente:
            if accion == "Salida":
                query_update = "UPDATE RegistrosAutos SET salida = ?, nombre_tecnico = ?, ultimo_mantenimiento = ? WHERE qr_code = ?"
                cursor.execute(query_update, (datetime.now().isoformat(), nombre_tecnico, ultimo_mantenimiento_dt.isoformat(), qr_code))
            elif accion == "Regreso":
                query_update = "UPDATE RegistrosAutos SET regreso = ?, nombre_tecnico = ?, ultimo_mantenimiento = ? WHERE qr_code = ?"
                cursor.execute(query_update, (datetime.now().isoformat(), nombre_tecnico, ultimo_mantenimiento_dt.isoformat(), qr_code))
        else:
            if accion == "Salida":
                query_insert = "INSERT INTO RegistrosAutos (qr_code, nombre_tecnico, ultimo_mantenimiento, salida) VALUES (?, ?, ?, ?)"
                cursor.execute(query_insert, (qr_code, nombre_tecnico, ultimo_mantenimiento_dt.isoformat(), datetime.now().isoformat()))
            else:
                logger.error(f"No se puede registrar regreso sin salida para QR: {qr_code}")
                return False

        conn.commit()
        logger.info("Datos guardados correctamente")
        return True
    except sqlite3.Error as e:
        logger.error(f"Error de base de datos en registrar_salida_regreso: {e}")
        return False
    except Exception as e:
        logger.error(f"Error general en registrar_salida_regreso: {e}")
        return False
    finally:
        conn.close()

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        nombre_tecnico = request.form['nombre_tecnico']
        ultimo_mantenimiento = request.form['ultimo_mantenimiento']
        qr_data = request.form['qr_data']
        accion = request.form['accion']

        logger.info(f"Datos recibidos para registrar: QR Code: {qr_data}, Persona: {nombre_tecnico}, Mantenimiento: {ultimo_mantenimiento}, Acción: {accion}")

        if not all([nombre_tecnico, ultimo_mantenimiento, qr_data, accion]):
            logger.error("Datos incompletos en el formulario")
            return render_template('index.html', error="Por favor, complete todos los campos.")

        try:
            if qr_data and registrar_salida_regreso(qr_data, nombre_tecnico, ultimo_mantenimiento, accion):
                return redirect(url_for('confirmacion', qr_data=qr_data, nombre_tecnico=nombre_tecnico, accion=accion))
            else:
                logger.error(f"Error en registrar_salida_regreso. Datos: {qr_data}, {nombre_tecnico}, {ultimo_mantenimiento}, {accion}")
                return render_template('index.html', error="Error en el registro. Por favor, intente nuevamente.")
        except Exception as e:
            logger.exception(f"Excepción no manejada en index: {str(e)}")
            return render_template('index.html', error="Error inesperado. Por favor, contacte al administrador.")

    # ... resto del código ...

    registros = []
    conn = create_connection()
    if conn is not None:
        try:
            cursor = conn.cursor()
            query_view = "SELECT id, qr_code, nombre_tecnico, ultimo_mantenimiento, salida, regreso FROM RegistrosAutos LIMIT 1000"
            cursor.execute(query_view)
            registros = cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Error al conectar o consultar la base de datos en index: {e}")
        finally:
            conn.close()

    return render_template('index.html', registros=registros)

@app.route('/lista')
def lista():
    registros = []
    conn = create_connection()
    if conn is not None:
        try:
            cursor = conn.cursor()
            query_view = "SELECT id, qr_code, nombre_tecnico, ultimo_mantenimiento, salida, regreso FROM RegistrosAutos LIMIT 1000"
            cursor.execute(query_view)
            registros = cursor.fetchall()
            logger.info("Registros obtenidos: %s", registros)
        except sqlite3.Error as e:
            logger.error(f"Error al conectar o consultar la base de datos en lista: {e}")
        finally:
            conn.close()

    return render_template('lista.html', registros=registros)

@app.route('/confirmacion')
def confirmacion():
    qr_data = request.args.get('qr_data')
    nombre_tecnico = request.args.get('nombre_tecnico')
    accion = request.args.get('accion')
    return render_template('confirmacion.html', qr_data=qr_data, nombre_tecnico=nombre_tecnico, accion=accion)

@app.route('/escaneo_qr', methods=['POST'])
def escaneo_qr():
    data = request.json
    image_base64 = data['image']
    qr_data = procesar_imagen_qr(image_base64)

    if qr_data:
        return jsonify({'success': True, 'qr_data': qr_data})
    else:
        return jsonify({'success': False, 'message': 'No se detectó ningún QR'})

def procesar_imagen_qr(image_base64):
    image_data = base64.b64decode(image_base64)
    np_arr = np.frombuffer(image_data, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    decoded_objects = decode(img)
    for obj in decoded_objects:
        qr_data = obj.data.decode('utf-8')
        return qr_data
    return None

@app.route('/verificar_qr', methods=['POST'])
def verificar_qr():
    data = request.json
    qr_code = data['qr_data']
    
    conn = create_connection()
    if conn is None:
        return jsonify({'error': 'Error al conectar con la base de datos'}), 500

    try:
        cursor = conn.cursor()
        query = "SELECT nombre_tecnico, ultimo_mantenimiento FROM RegistrosAutos WHERE qr_code = ?"
        cursor.execute(query, (qr_code,))
        resultado = cursor.fetchone()

        if resultado:
            nombre_tecnico, ultimo_mantenimiento = resultado
            return jsonify({
                'exists': True,
                'nombre_tecnico': nombre_tecnico,
                'ultimo_mantenimiento': ultimo_mantenimiento
            })
        else:
            return jsonify({'exists': False})

    except sqlite3.Error as e:
        logger.error(f"Error al verificar QR en la base de datos: {e}")
        return jsonify({'error': 'Error al verificar QR'}), 500
    finally:
        conn.close()

@app.route('/checklist', methods=['GET', 'POST'])
def checklist():
    if request.method == 'POST':
        numero_coche = request.form['numero_coche']
        kilometraje = request.form['kilometraje']
        estado_llantas = request.form['estado_llantas']
        estado_rines = request.form['estado_rines']
        detalles_raspones = request.form['detalles_raspones']
        estado_faros = request.form['estado_faros']
        otros_detalles = request.form['otros_detalles']
        
        conn = create_connection()
        if conn is None:
            return redirect(url_for('checklist', error="Error al conectar con la base de datos"))

        try:
            cursor = conn.cursor()
            
            cursor.execute("SELECT 1 FROM CheckListAutos WHERE numero_coche = ?", (numero_coche,))
            exists = cursor.fetchone()
            
            if exists:
                query = """
                UPDATE CheckListAutos 
                SET kilometraje = ?, estado_llantas = ?, estado_rines = ?, 
                    detalles_raspones = ?, estado_faros = ?, otros_detalles = ?,
                    ultima_actualizacion = CURRENT_TIMESTAMP
                WHERE numero_coche = ?
                """
                cursor.execute(query, (kilometraje, estado_llantas, estado_rines, 
                                       detalles_raspones, estado_faros, otros_detalles, 
                                       numero_coche))
            else:
                query = """
                INSERT INTO CheckListAutos (numero_coche, kilometraje, estado_llantas, estado_rines, 
                                            detalles_raspones, estado_faros, otros_detalles)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """
                cursor.execute(query, (numero_coche, kilometraje, estado_llantas, estado_rines, 
                                       detalles_raspones, estado_faros, otros_detalles))
            
            conn.commit()
            return redirect(url_for('checklist', message="Checklist actualizado correctamente"))
        except sqlite3.Error as e:
            logger.error(f"Error al actualizar el checklist: {e}")
            return redirect(url_for('checklist', error="Error al actualizar el checklist"))
        finally:
            conn.close()
    
    coches = []
    conn = create_connection()
    if conn is not None:
        try:
            cursor = conn.cursor()
            query = "SELECT numero_coche FROM CheckListAutos"
            cursor.execute(query)
            coches = [row[0] for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"Error al obtener la lista de coches: {e}")
        finally:
            conn.close()
    
    return render_template('checklist.html', coches=coches, message=request.args.get('message'), error=request.args.get('error'))

@app.route('/get_car_details/<string:numero_coche>')
def get_car_details(numero_coche):
    conn = create_connection()
    if conn is None:
        return jsonify({"error": "Error al conectar con la base de datos"}), 500

    try:
        cursor = conn.cursor()
        query = """
        SELECT numero_coche, kilometraje, estado_llantas, estado_rines, 
               detalles_raspones, estado_faros, otros_detalles, ultima_actualizacion 
        FROM CheckListAutos 
        WHERE numero_coche = ?
        """
        cursor.execute(query, (numero_coche,))
        car = cursor.fetchone()
        if car:
            return jsonify({
                "numero_coche": car[0],
                "kilometraje": car[1] or "",
                "estado_llantas": car[2] or "",
                "estado_rines": car[3] or "",
                "detalles_raspones": car[4] or "",
                "estado_faros": car[5] or "",
                "otros_detalles": car[6] or "",
                "ultima_actualizacion": car[7] or ""
            })
        else:
            return jsonify({"error": "Coche no encontrado"}), 404
    except sqlite3.Error as e:
        logger.error(f"Error al obtener detalles del coche: {e}")
        return jsonify({"error": "Error al obtener detalles del coche"}), 500
    finally:
        conn.close()

if __name__ == '__main__':
    app.run(host = "0.0.0.0" , port=5000)