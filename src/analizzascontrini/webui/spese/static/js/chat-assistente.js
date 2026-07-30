document.addEventListener("DOMContentLoaded", () => {

    const chatToggle = document.getElementById("chat-toggle");
    const chatWindow = document.getElementById("chat-window");
    const chatMessages = document.getElementById("chat-messages");
    const chatForm = document.getElementById("chat-form");
    const chatInput = document.getElementById("chat-input");

    let chatTaskId = null;
    let chatWs = null;

    // ============================================
    // OPEN / CLOSE CHAT
    // ============================================

    chatToggle.addEventListener("click", () => {
        chatWindow.classList.toggle("d-none");

        if (!chatWindow.classList.contains("d-none")) {
            chatInput.focus();

            // Loading chat only first time
            if (!chatTaskId) {
                caricaChat();
            }
        }
    });

    // ============================================
    // LOADING CHAT
    // ============================================

    async function caricaChat() {
        try {
            const response = await fetch("/api/chat/", {
                method: "GET",
                headers: {
                    "X-Requested-With": "XMLHttpRequest"
                }
            });

            if (!response.ok) {
                throw new Error("Errore nel caricamento della chat");
            }

            const data = await response.json();
            chatTaskId = data.task_id;

            renderMessaggi(data.data.messages || []);

            // start WebSocket
            avviaWebSocket(data);

        } catch (error) {
            console.error("Errore caricamento chat:", error);
            aggiungiMessaggio({
                role: "assistant",
                content: "Errore nel caricamento della chat."
            });
        }
    }

    // ============================================
    // RENDER MESSAGE
    // ============================================

    function renderMessaggi(messages) {
        chatMessages.innerHTML = "";
        messages.forEach(message => {
            aggiungiMessaggio(message);
        });
        scrollInBasso();
    }

    function aggiungiMessaggio(message) {
        const div = document.createElement("div");
        div.classList.add("chat-message", "mb-2", "p-2", "rounded");

        if (message.role === "user") {
            div.classList.add("bg-primary", "text-white", "ms-auto");
        } else {
            div.classList.add("bg-light", "text-dark");
        }

        div.textContent = message.content;
        chatMessages.appendChild(div);
        scrollInBasso();
    }

    function scrollInBasso() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // ============================================
    // WEBSOCKET
    // ============================================

    function avviaWebSocket(data) {
        const wsManager = new TaskWebSocketManager(
            data.task_id,
            data.status, 
            {
                onProcessing: async (eventData) => {
                    //console.log("[CHAT] Aggiornamento task:", eventData);

                    if (eventData.step === "Risposta inviata") {
                        console.log("[CHAT] Risposta pronta, ricarico la chat...");
                        await caricaChat();
                    }
                },
                onCompleted: (eventData) => {
                    //console.log("[CHAT] Chat completata:", eventData);
                },
                onFailed: (eventData) => {
                    console.error("[CHAT] Errore:", eventData);
                }
            }
        );
        wsManager.start();
    }

    // ============================================
    // SEND MESSAGE
    // ============================================

    chatForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        //console.log("[CHAT] SUBMIT PARTITO");

        const testo = chatInput.value.trim();
        //console.log("[CHAT] Testo:", testo);

        if (!testo) {
            return;
        }

        try {
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

            const response = await fetch("/api/chat/send/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken
                },
                
                body: JSON.stringify({
                    message: testo
                })
            });

            //console.log("[CHAT] Risposta HTTP:", response.status);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || "Errore nell'invio del messaggio");
            }

            //console.log("[CHAT] Messaggio inviato:", data);


            aggiungiMessaggio({
                role: "user",
                content: testo
            });

            chatInput.value = "";

        } catch (error) {
            console.error("[CHAT] Errore invio messaggio:", error);
        }
    });
});