/**
 * TaskWebSocketManager
 * Manages the WebSocket connection for processing tasks.
 */
class TaskWebSocketManager {
    constructor(taskId, initialState, options = {}) {
        this.taskId = taskId;
        this.initialState = initialState;
        this.socket = null;
        
        // Callback 
        this.onProcessing = options.onProcessing || (() => {});
        this.onCompleted = options.onCompleted || (() => {});
        this.onFailed = options.onFailed || (() => {});
        this.onError = options.onError || ((err) => console.error("WS Error:", err));
    }

    start() {
        const state = (this.initialState || "").trim().toUpperCase();

        if (state === "COMPLETED") {
            //console.log(`[WS Manager] Task ${this.taskId} già COMPLETED.`);
            this.onCompleted({ status: "COMPLETED" });
            return;
        }
        
        if (state === "FAILED") {
            //console.log(`[WS Manager] Task ${this.taskId} già FAILED.`);
            this.onFailed({ status: "FAILED", error: "Task fallito (controlla i log)" });
            return;
        }

        const wsScheme = window.location.protocol === "https:" ? "wss" : "ws";
        const wsUrl = `${wsScheme}://${window.location.host}/ws/task/${this.taskId}/`;
        
        //console.log(`[WS Manager] Connessione a: ${wsUrl}`);
        this.socket = new WebSocket(wsUrl);

        this.socket.onmessage = (e) => this._handleMessage(e);
        this.socket.onclose = () => console.log(`[WS Manager] Connessione chiusa per task ${this.taskId}`);
        this.socket.onerror = (err) => this.onError(err);
    }

    _handleMessage(e) {
        const data = JSON.parse(e.data);
        //console.log("[WS Manager] Ricevuto update:", data);

     
        if (data.status === "FAILED") {
            this.onFailed(data);
            this.close();
        } else if (data.status === "COMPLETED") {
            this.onCompleted(data);
            this.close();
        } else {
            this.onProcessing(data);
        }
    }

    close() {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.close();
        }
    }
}