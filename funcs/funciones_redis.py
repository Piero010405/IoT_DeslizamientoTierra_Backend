"""
Sensor Cache Manager - Gestor de Caché Redis optimizado para datos de sensores en tiempo real
"""
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import redis

class SensorCacheManager:
    """
    Gestor de caché Redis optimizado para datos de sensores en tiempo real
    """

    def __init__(self, host='localhost', port=6379, db=0):
        self.redis_client = redis.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=True
        )

        # Configuración de TTL (en segundos)
        self.TTL_ESTADO_ACTUAL = 3600  # 1 hora - estado más reciente
        self.TTL_HISTORICO_RECIENTE = 86400  # 24 horas - últimas lecturas
        self.TTL_ALERTAS_ACTIVAS = 7200  # 2 horas - alertas sin resolver

    # ============ SENSOR DE VIBRACIÓN ============

    def guardar_vibracion(self, sensor_id: str, pulse: int, hit: int):
        """
        Guarda datos de sensor de vibración
        pulse: número de pulsos
        hit: 0 o 1 (detección de golpe)
        """
        timestamp = datetime.now().isoformat()

        # 1. Estado actual del sensor (clave simple, se sobrescribe)
        estado_key = f"sensor:vibracion:{sensor_id}:actual"
        estado = {
            'pulse': pulse,
            'hit': hit,
            'timestamp': timestamp,
            'tipo': 'vibracion'
        }
        self.redis_client.setex(
            estado_key,
            self.TTL_ESTADO_ACTUAL,
            json.dumps(estado)
        )

        # 2. Agregar a histórico reciente (lista con las últimas 100 lecturas)
        historico_key = f"sensor:vibracion:{sensor_id}:historico"
        self.redis_client.lpush(historico_key, json.dumps(estado))
        self.redis_client.ltrim(historico_key, 0, 99)  # Mantener solo 100
        self.redis_client.expire(historico_key, self.TTL_HISTORICO_RECIENTE)

        # 3. Si hay hit, generar alerta
        if hit == 1:
            self._generar_alerta(sensor_id, 'vibracion', f'Golpe detectado (pulse: {pulse})')

        # 4. Estadísticas en tiempo real (usando Sorted Set)
        stats_key = f"sensor:vibracion:{sensor_id}:stats"
        self.redis_client.zadd(
            stats_key,
            {timestamp: pulse},
            nx=False
        )
        # Mantener solo últimos 1000 registros
        self.redis_client.zremrangebyrank(stats_key, 0, -1001)
        self.redis_client.expire(stats_key, self.TTL_HISTORICO_RECIENTE)

        return True
    # ============ SENSOR DE INCLINACIÓN ============

    def guardar_inclinacion(self, sensor_id: str, estado: int):
        """
        Guarda estado de sensor de inclinación
        estado: 0 (normal) o 1 (inclinado)
        """
        timestamp = datetime.now().isoformat()

        estado_key = f"sensor:inclinacion:{sensor_id}:actual"
        data = {
            'estado': estado,
            'timestamp': timestamp,
            'tipo': 'inclinacion'
        }
        self.redis_client.setex(
            estado_key,
            self.TTL_ESTADO_ACTUAL,
            json.dumps(data)
        )

        # Histórico
        historico_key = f"sensor:inclinacion:{sensor_id}:historico"
        self.redis_client.lpush(historico_key, json.dumps(data))
        self.redis_client.ltrim(historico_key, 0, 99)
        self.redis_client.expire(historico_key, self.TTL_HISTORICO_RECIENTE)

        # Alerta si cambió a inclinado
        if estado == 1:
            estado_previo = self.obtener_estado_actual(sensor_id, 'inclinacion')
            if estado_previo and estado_previo.get('estado') == 0:
                self._generar_alerta(sensor_id, 'inclinacion', 'Cambio de posición detectado')

        return True

    # ============ SENSOR DE HUMEDAD ============

    def guardar_humedad(self, sensor_id: str, porcentaje: float, valor_raw: int):
        """
        Guarda datos de sensor de humedad
        porcentaje: valor de humedad en %
        valor_raw: valor bruto del sensor (0-1024)
        """
        timestamp = datetime.now().isoformat()

        estado_key = f"sensor:humedad:{sensor_id}:actual"
        data = {
            'porcentaje': porcentaje,
            'valor_raw': valor_raw,
            'timestamp': timestamp,
            'tipo': 'humedad'
        }
        self.redis_client.setex(
            estado_key,
            self.TTL_ESTADO_ACTUAL,
            json.dumps(data)
        )

        # Histórico
        historico_key = f"sensor:humedad:{sensor_id}:historico"
        self.redis_client.lpush(historico_key, json.dumps(data))
        self.redis_client.ltrim(historico_key, 0, 99)
        self.redis_client.expire(historico_key, self.TTL_HISTORICO_RECIENTE)

        # Promedios móviles (últimos 10 minutos)
        promedio_key = f"sensor:humedad:{sensor_id}:promedio"
        self.redis_client.zadd(
            promedio_key,
            {timestamp: porcentaje},
            nx=False
        )
        # Eliminar registros más antiguos de 10 minutos
        hace_10_min = (datetime.now() - timedelta(minutes=10)).isoformat()
        self.redis_client.zremrangebyscore(promedio_key, '-inf', f'({hace_10_min}')
        self.redis_client.expire(promedio_key, self.TTL_HISTORICO_RECIENTE)

        # Alertas por umbrales
        if porcentaje > 80:
            self._generar_alerta(sensor_id, 'humedad', f'Humedad alta: {porcentaje}%')
        elif porcentaje < 20:
            self._generar_alerta(sensor_id, 'humedad', f'Humedad baja: {porcentaje}%')

        return True

    # ============ GESTIÓN DE ALERTAS ============

    def _generar_alerta(self, sensor_id: str, tipo_sensor: str, mensaje: str):
        """
        Genera una alerta y la almacena en caché
        """
        timestamp = datetime.now().isoformat()
        alerta_id = f"{sensor_id}:{tipo_sensor}:{int(time.time())}"

        alerta = {
            'id': alerta_id,
            'sensor_id': sensor_id,
            'tipo_sensor': tipo_sensor,
            'mensaje': mensaje,
            'timestamp': timestamp,
            'activa': True,
            'resuelta': False
        }

        # Guardar alerta individual
        alerta_key = f"alerta:{alerta_id}"
        self.redis_client.setex(
            alerta_key,
            self.TTL_ALERTAS_ACTIVAS,
            json.dumps(alerta)
        )

        # Agregar a set de alertas activas
        alertas_activas_key = "alertas:activas"
        self.redis_client.sadd(alertas_activas_key, alerta_id)

        # Publicar en canal Pub/Sub para notificaciones en tiempo real
        self.redis_client.publish('canal:alertas', json.dumps(alerta))

        return alerta_id

    def resolver_alerta(self, alerta_id: str):
        """Marca una alerta como resuelta"""
        alerta_key = f"alerta:{alerta_id}"
        alerta_data = self.redis_client.get(alerta_key)

        if alerta_data:
            alerta = json.loads(alerta_data)
            alerta['resuelta'] = True
            alerta['activa'] = False
            alerta['timestamp_resolucion'] = datetime.now().isoformat()

            self.redis_client.setex(alerta_key, self.TTL_ALERTAS_ACTIVAS, json.dumps(alerta))
            self.redis_client.srem("alertas:activas", alerta_id)

            return True
        return False

    def obtener_alertas_activas(self) -> List[Dict]:
        """Obtiene todas las alertas activas"""
        alertas_ids = self.redis_client.smembers("alertas:activas")
        alertas = []

        for alerta_id in alertas_ids:
            alerta_key = f"alerta:{alerta_id}"
            alerta_data = self.redis_client.get(alerta_key)
            if alerta_data:
                alertas.append(json.loads(alerta_data))

        return alertas

    # ============ CONSULTAS ============

    def obtener_estado_actual(self, sensor_id: str, tipo_sensor: str) -> Optional[Dict]:
        """Obtiene el estado actual de un sensor"""
        key = f"sensor:{tipo_sensor}:{sensor_id}:actual"
        data = self.redis_client.get(key)
        return json.loads(data) if data else None

    def obtener_historico_reciente(self, sensor_id: str, tipo_sensor: str, limite: int = 50) -> List[Dict]:
        """Obtiene el histórico reciente de un sensor"""
        key = f"sensor:{tipo_sensor}:{sensor_id}:historico"
        datos = self.redis_client.lrange(key, 0, limite - 1)
        return [json.loads(d) for d in datos]

    def obtener_promedio_humedad(self, sensor_id: str) -> Optional[float]:
        """Calcula el promedio de humedad de los últimos 10 minutos"""
        key = f"sensor:humedad:{sensor_id}:promedio"
        valores = self.redis_client.zrange(key, 0, -1, withscores=True)

        if not valores:
            return None

        total = sum(float(score) for _, score in valores)
        return round(total / len(valores), 2)

    def obtener_dashboard(self) -> Dict:
        """
        Obtiene un resumen general de todos los sensores para dashboard
        """
        dashboard = {
            'timestamp': datetime.now().isoformat(),
            'sensores': {
                'vibracion': [],
                'inclinacion': [],
                'humedad': []
            },
            'alertas_activas': self.obtener_alertas_activas(),
            'total_alertas': len(self.obtener_alertas_activas())
        }

        # Buscar todos los sensores activos
        for tipo in ['vibracion', 'inclinacion', 'humedad']:
            pattern = f"sensor:{tipo}:*:actual"
            for key in self.redis_client.scan_iter(match=pattern):
                data = self.redis_client.get(key)
                if data:
                    sensor_info = json.loads(data)
                    sensor_id = key.split(':')[2]
                    sensor_info['sensor_id'] = sensor_id
                    dashboard['sensores'][tipo].append(sensor_info)

        return dashboard

    # ============ MANTENIMIENTO ============

    def limpiar_datos_expirados(self):
        """Limpieza manual de datos expirados (Redis lo hace automáticamente, pero esto es un respaldo)"""
        # Esta función es más para limpieza específica si es necesario
        alertas_resueltas = []
        for alerta_id in self.redis_client.smembers("alertas:activas"):
            alerta_key = f"alerta:{alerta_id}"
            alerta_data = self.redis_client.get(alerta_key)
            if alerta_data:
                alerta = json.loads(alerta_data)
                if alerta.get('resuelta'):
                    alertas_resueltas.append(alerta_id)
        
        if alertas_resueltas:
            self.redis_client.srem("alertas:activas", *alertas_resueltas)
        
        return len(alertas_resueltas)


# ============ EJEMPLO DE USO ============

if __name__ == "__main__":
    # Inicializar el gestor
    cache = SensorCacheManager()

    print("=== Simulación de Datos de Sensores ===\n")

    # 1. Sensor de vibración
    print("1. Guardando datos de vibración...")
    cache.guardar_vibracion("sensor_vib_001", pulse=150, hit=0)
    cache.guardar_vibracion("sensor_vib_001", pulse=180, hit=1)  # Genera alerta

    # 2. Sensor de inclinación
    print("2. Guardando datos de inclinación...")
    cache.guardar_inclinacion("sensor_inc_001", estado=0)
    time.sleep(0.1)
    cache.guardar_inclinacion("sensor_inc_001", estado=1)  # Genera alerta

    # 3. Sensor de humedad
    print("3. Guardando datos de humedad...")
    cache.guardar_humedad("sensor_hum_001", porcentaje=45.5, valor_raw=512)
    cache.guardar_humedad("sensor_hum_001", porcentaje=85.2, valor_raw=920)  # Genera alerta

    # Consultar estado actual
    print("\n=== Estados Actuales ===")
    estado_vib = cache.obtener_estado_actual("sensor_vib_001", "vibracion")
    print(f"Vibración: {estado_vib}")

    estado_inc = cache.obtener_estado_actual("sensor_inc_001", "inclinacion")
    print(f"Inclinación: {estado_inc}")

    estado_hum = cache.obtener_estado_actual("sensor_hum_001", "humedad")
    print(f"Humedad: {estado_hum}")

    # Promedio de humedad
    promedio = cache.obtener_promedio_humedad("sensor_hum_001")
    print(f"\nPromedio humedad (últimos 10 min): {promedio}%")

    # Ver alertas activas
    print("\n=== Alertas Activas ===")
    alertas = cache.obtener_alertas_activas()
    for alerta in alertas:
        print(f"- [{alerta['tipo_sensor']}] {alerta['mensaje']}")

    # Dashboard completo
    print("\n=== Dashboard Completo ===")
    dashboard = cache.obtener_dashboard()
    print(f"Total de alertas activas: {dashboard['total_alertas']}")
    print(f"Sensores de vibración activos: {len(dashboard['sensores']['vibracion'])}")
    print(f"Sensores de inclinación activos: {len(dashboard['sensores']['inclinacion'])}")
    print(f"Sensores de humedad activos: {len(dashboard['sensores']['humedad'])}")
