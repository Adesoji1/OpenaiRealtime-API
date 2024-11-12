// src/components/AudioRecorder.jsx
import React from 'react';
import { ReactMediaRecorder } from 'react-media-recorder';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faMicrophone, faStopCircle } from '@fortawesome/free-solid-svg-icons';

const AudioRecorder = ({ socket }) => {
  return (
    <div className="audio-recorder">
      <ReactMediaRecorder
        audio
        blobPropertyBag={{ type: 'audio/webm' }}
        onStop={(blobUrl, blob) => {
          // Convert the Blob to an ArrayBuffer and send it to the backend
          blob.arrayBuffer().then((buffer) => {
            if (socket && socket.readyState === WebSocket.OPEN) {
              socket.send(buffer);
            }
          });
        }}
        render={({ status, startRecording, stopRecording, mediaBlobUrl }) => (
          <div>
            <p>{status}</p>
            <button className="record-button" onClick={startRecording}>
              <FontAwesomeIcon icon={faMicrophone} size="2x" />
            </button>
            <button className="record-button" onClick={stopRecording}>
              <FontAwesomeIcon icon={faStopCircle} size="2x" />
            </button>
            {/* Optionally, you can include an audio player to play back the recording but i am yet to implement thus */}
            {/* {mediaBlobUrl && <audio src={mediaBlobUrl} controls />} */}
          </div>
        )}
      />
    </div>
  );
};

export default AudioRecorder;
