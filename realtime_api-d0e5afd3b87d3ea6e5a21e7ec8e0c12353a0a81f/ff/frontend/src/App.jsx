// App.jsx
import React, { useState, useEffect, useRef } from 'react';
import './App.css';
import { v4 as uuidv4 } from 'uuid';

function App() {
  const [messages, setMessages] = useState([]);
  const [recording, setRecording] = useState(false);
  const [inputText, setInputText] = useState('');
  const [organization, setOrganization] = useState('organization1');
  const [requestId, setRequestId] = useState(uuidv4());
  const wsRef = useRef(null);
  const mediaRecorderRef = useRef(null);

  // Download chat history
  const downloadChatHistory = () => {
    wsRef.current.send(JSON.stringify({ text: "DOWNLOAD_CHAT_HISTORY_BUTTON_CLICKED" }));
    setMessages((prev) => [...prev, { sender: "System", text: "Requested chat history download." }]);
  };

  // Handle organization change
  const handleOrganizationChange = (event) => {
    setOrganization(event.target.value);
    setRequestId(uuidv4()); // Generate a new requestId when organization changes
  };

  useEffect(() => {
    // Close existing WebSocket if open
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.close();
    }

    // Initialize WebSocket
    const ws = new WebSocket(`ws://localhost:8000/gpt-api/chat_stream/${organization}/${requestId}`);
    ws.onopen = () => console.log("Connected to backend WebSocket");
    ws.onmessage = handleMessage;
    ws.onclose = () => console.log("Disconnected from backend WebSocket");
    ws.onerror = (error) => console.error("WebSocket error:", error);
    wsRef.current = ws;

    return () => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    };
  }, [organization, requestId]);

  const handleMessage = (event) => {
    const message = typeof event.data === "string" ? JSON.parse(event.data) : null;

    if (message) {
      if (message.text) {
        setMessages((prev) => [...prev, { sender: "AI", text: message.text }]);
      } else if (message.chat_history) {
        // Handle chat history download
        console.log("Received chat history:", message.chat_history);
        const element = document.createElement("a");
        const file = new Blob([JSON.stringify(message.chat_history, null, 2)], { type: 'application/json' });
        element.href = URL.createObjectURL(file);
        element.download = "chat_history.json";
        document.body.appendChild(element);
        element.click();
        document.body.removeChild(element);
      } else if (message.error) {
        alert(`Error: ${message.error}`);
      }
    } else if (event.data instanceof Blob || event.data instanceof ArrayBuffer) {
      // Handle audio data
      const audioUrl = URL.createObjectURL(event.data);
      const audio = new Audio(audioUrl);
      audio.play().catch((e) => {
        console.error("Failed to play audio:", e);
      });
      setMessages((prev) => [...prev, { sender: "AI", audioUrl }]);
      audio.onended = () => {
        URL.revokeObjectURL(audioUrl);
      };
    }
  };

  const sendMessage = () => {
    if (inputText.trim() !== "") {
      wsRef.current.send(JSON.stringify({ text: inputText }));
      setMessages((prev) => [...prev, { sender: "You", text: inputText }]);
      setInputText("");
    }
  };

  const sendDocumentSignal = () => {
    wsRef.current.send(JSON.stringify({ text: "DOCUMENT_SENT:Sample Document" }));
    setMessages((prev) => [...prev, { sender: "System", text: "Sent a document." }]);
  };

  const sendImageSignal = () => {
    wsRef.current.send(JSON.stringify({ text: "IMAGE_SENT:Sample Image" }));
    setMessages((prev) => [...prev, { sender: "System", text: "Sent an image." }]);
  };

  const startRecording = async () => {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      console.error('MediaDevices API or getUserMedia not supported.');
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);

      mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          wsRef.current.send(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorder.start(7000); // Send data every 7s
      mediaRecorderRef.current = mediaRecorder;
      setRecording(true);
    } catch (err) {
      console.error('Error accessing microphone:', err);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current = null;
      setRecording(false);
    }
  };

  return (
    <div className="app-container">
      <h1>Voice Chat with AI</h1>
      <div className="organization-selector">
        <label htmlFor="organization">Select Organization:</label>
        <select id="organization" value={organization} onChange={handleOrganizationChange}>
          <option value="organization1">Organization 1</option>
          <option value="organization2">Organization 2</option>
        </select>
      </div>
      <div className="chat-container">
        {messages.map((msg, index) => (
          <div key={index} className={`message ${msg.sender === "You" ? "sent" : "received"}`}>
            {msg.text && (
              <div className="message-bubble">
                <strong>{msg.sender}:</strong> {msg.text}
              </div>
            )}
            {msg.audioUrl && (
              <audio src={msg.audioUrl} controls />
            )}
          </div>
        ))}
      </div>
      <textarea 
        value={inputText} 
        onChange={(e) => setInputText(e.target.value)} 
        placeholder="Type your message... or 🎤 (Record)" 
      />
      <button onClick={sendMessage}>Send</button>
      <button onClick={sendDocumentSignal}>Send Document</button>
      <button onClick={sendImageSignal}>Send Image</button>
      <button onClick={downloadChatHistory}>Download Chat History</button>
      {recording ? (
        <button onClick={stopRecording}>Stop Recording</button>
      ) : (
        <button onClick={startRecording}>Start Recording</button>
      )}
    </div>
  );
}

export default App;
