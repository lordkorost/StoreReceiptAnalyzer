import json
from channels.generic.websocket import AsyncWebsocketConsumer

class TaskConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        #  /ws/task/<task_id>/
        self.task_id = self.scope['url_route']['kwargs']['task_id']
        self.group_name = f"task_{self.task_id}"

        # Join task group
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    
    async def task_update(self, event):
        await self.send(text_data=json.dumps({
            "status": event["status"],
            "progress": event["progress"],
            "error": event["error"],
            "step": event["step"]  
        }))