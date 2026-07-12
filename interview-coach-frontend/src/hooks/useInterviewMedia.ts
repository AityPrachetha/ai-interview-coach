import { useCallback, useEffect, useRef, useState } from 'react';

export type MediaStatus = 'idle' | 'requesting' | 'ready' | 'error';

/**
 * Requests camera+mic ONCE and keeps a single continuous MediaStream alive
 * for the whole interview (the video preview never stops between
 * questions) - this hook just exposes ways to sample from that stream:
 * grab a single frame as a JPEG blob, or record a stretch of the audio
 * track as a standalone clip.
 */
export function useInterviewMedia() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const [status, setStatus] = useState<MediaStatus>('idle');
  const [error, setError] = useState<string | null>(null);

  const start = useCallback(async () => {
    setStatus('requesting');
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play().catch(() => {
          // Some browsers require a user gesture before autoplay - the
          // element still shows a frame once the person interacts with it.
        });
      }
      setStatus('ready');
    } catch {
      setError(
        'Could not access your camera/microphone. Check your browser permissions and try again.',
      );
      setStatus('error');
    }
  }, []);

  const stop = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setStatus('idle');
  }, []);

  const captureFrameBlob = useCallback((): Promise<Blob | null> => {
    const video = videoRef.current;
    return new Promise((resolve) => {
      if (!video || video.videoWidth === 0) {
        resolve(null);
        return;
      }
      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        resolve(null);
        return;
      }
      ctx.drawImage(video, 0, 0);
      canvas.toBlob((blob) => resolve(blob), 'image/jpeg', 0.8);
    });
  }, []);

  const startAudioRecording = useCallback(() => {
    const stream = streamRef.current;
    if (!stream) return;
    const audioOnly = new MediaStream(stream.getAudioTracks());
    chunksRef.current = [];
    const mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : '';
    const recorder = mimeType ? new MediaRecorder(audioOnly, { mimeType }) : new MediaRecorder(audioOnly);
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };
    recorder.start();
    recorderRef.current = recorder;
  }, []);

  const stopAudioRecording = useCallback((): Promise<Blob> => {
    return new Promise((resolve) => {
      const recorder = recorderRef.current;
      if (!recorder || recorder.state === 'inactive') {
        resolve(new Blob([], { type: 'audio/webm' }));
        return;
      }
      recorder.onstop = () => {
        resolve(new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' }));
      };
      recorder.stop();
    });
  }, []);

  // Always release the camera/mic when the interview page unmounts.
  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  return {
    videoRef,
    status,
    error,
    start,
    stop,
    captureFrameBlob,
    startAudioRecording,
    stopAudioRecording,
  };
}
