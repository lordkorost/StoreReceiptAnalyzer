from django.urls import path
from spese.consumers import TaskConsumer

websocket_urlpatterns = [
    path('ws/task/<int:task_id>/', TaskConsumer.as_asgi()),
]