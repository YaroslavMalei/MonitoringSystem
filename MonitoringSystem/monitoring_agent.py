import socket
import time
import threading
from flask import Flask, Response
import psutil
import requests

app = Flask(__name__)

# Отримуємо ім'я хоста
HOSTNAME = socket.gethostname()

# Лічильник для реальних запитів до сервера
REQUEST_COUNTER = 0

# Об'єкт для синхронізації потоків
lock = threading.Lock()

# Змінна для зберігання часу відповіді сервера
last_response_time_ms = 0

# Збільшуємо лічильник для кожного вхідного запиту
@app.before_request
def count_requests():
    global REQUEST_COUNTER
    with lock:
        REQUEST_COUNTER += 1

# Функція для збору системних метрик
def collect_metrics():
    global REQUEST_COUNTER
    metrics = []

    # CPU
    cpu_usage = psutil.cpu_percent(interval=1)
    metrics.append(f'system_cpu_usage_percent{{host="{HOSTNAME}"}} {cpu_usage}')

    # RAM (у байтах)
    mem = psutil.virtual_memory()
    metrics.append(f'system_memory_total_bytes{{host="{HOSTNAME}"}} {mem.total}')
    metrics.append(f'system_memory_used_bytes{{host="{HOSTNAME}"}} {mem.used}')
    metrics.append(f'system_memory_free_bytes{{host="{HOSTNAME}"}} {mem.available}')

    # Диск (у байтах)
    for disk_letter in ['C:\\', 'D:\\']:
        try:
            disk = psutil.disk_usage(disk_letter)
            label = disk_letter.rstrip('\\').lower()
            metrics.append(f'system_disk_total_bytes{{host="{HOSTNAME}",disk="{label}"}} {disk.total}')
            metrics.append(f'system_disk_used_bytes{{host="{HOSTNAME}",disk="{label}"}} {disk.used}')
            metrics.append(f'system_disk_free_bytes{{host="{HOSTNAME}",disk="{label}"}} {disk.free}')
        except FileNotFoundError:
            pass

    # Незвична перевірка статусу мережі: час відгуку
    try:
        start_time = time.time()
        response = requests.get("https://google.com", timeout=3)
        end_time = time.time()
        latency_ms = (end_time - start_time) * 1000  # Переводимо в мілісекунди
        metrics.append(f'system_network_latency_ms{{host="{HOSTNAME}"}} {latency_ms:.2f}')
    except requests.RequestException:
        metrics.append(f'system_network_latency_ms{{host="{HOSTNAME}"}} -1.00')  # -1 для відсутності з'єднання

    # Кількість активних процесів
    process_count = len(psutil.pids())
    metrics.append(f'system_active_processes_count{{host="{HOSTNAME}"}} {process_count}')

    # Час відповіді сервера
    with lock:
        metrics.append(f'system_server_response_time_ms{{host="{HOSTNAME}"}} {last_response_time_ms}')

    # Загальна кількість запитів
    with lock:
        metrics.append(f'system_server_request_count{{host="{HOSTNAME}"}} {REQUEST_COUNTER}')

    return "\n".join(metrics)

# Ендпоінт для метрик
@app.route("/metrics")
def metrics():
    global last_response_time_ms
    start_time = time.time()
    output = collect_metrics()
    end_time = time.time()
    with lock:
        last_response_time_ms = (end_time - start_time) * 1000

    return Response(output, mimetype="text/plain")

# Запускаємо сервер
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
