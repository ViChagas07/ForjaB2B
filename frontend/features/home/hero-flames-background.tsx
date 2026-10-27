"use client";

import { useEffect, useRef, useState } from "react";

const FLAMES_VIDEO_SRC = "/brand/forja-flames-enhanced.mp4";
const FLAMES_POSTER_SRC = "/brand/forja-flames-poster.jpg";
const FLAMES_PLAYBACK_RATE = 0.75;

const BACKGROUND_LAYER_CLASS =
  "pointer-events-none absolute inset-0 h-full w-full object-cover object-center";

export function HeroFlamesBackground() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [videoFailed, setVideoFailed] = useState(false);
  const [posterFailed, setPosterFailed] = useState(false);

  useEffect(() => {
    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const handleChange = () => setReducedMotion(mediaQuery.matches);
    handleChange();
    mediaQuery.addEventListener("change", handleChange);
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, []);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || reducedMotion || videoFailed) return;

    const handleError = () => setVideoFailed(true);
    video.addEventListener("error", handleError);

    if (video.error) {
      handleError();
      return () => video.removeEventListener("error", handleError);
    }

    const startPlayback = () => {
      if (video.error) {
        handleError();
        return;
      }
      video.muted = true;
      video.playbackRate = FLAMES_PLAYBACK_RATE;
      video.play().catch(() => {});
    };

    startPlayback();
    video.addEventListener("loadedmetadata", startPlayback);
    return () => {
      video.removeEventListener("error", handleError);
      video.removeEventListener("loadedmetadata", startPlayback);
    };
  }, [reducedMotion, videoFailed]);

  const showStaticFallback = reducedMotion || videoFailed;

  if (showStaticFallback && !posterFailed) {
    return (
      <img
        src={FLAMES_POSTER_SRC}
        alt=""
        aria-hidden="true"
        draggable={false}
        onError={() => setPosterFailed(true)}
        className={BACKGROUND_LAYER_CLASS}
      />
    );
  }

  if (showStaticFallback) {
    return null;
  }

  return (
    <video
      ref={videoRef}
      src={FLAMES_VIDEO_SRC}
      poster={FLAMES_POSTER_SRC}
      autoPlay
      loop
      muted
      playsInline
      preload="metadata"
      disablePictureInPicture
      disableRemotePlayback
      aria-hidden="true"
      onError={() => setVideoFailed(true)}
      className={BACKGROUND_LAYER_CLASS}
    />
  );
}
