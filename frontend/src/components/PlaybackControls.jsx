export default function PlaybackControls({ playback, ready }) {
  const { cursor, length, playing, delay } = playback;
  return (
    <section className="playback" aria-label="Playback controls">
      <div className="playback-buttons">
        <button className="button" disabled={!ready || cursor === 0} onClick={playback.previous}>Previous</button>
        <button className="primary-button play-button" disabled={!ready || cursor === length} onClick={playing ? playback.pause : playback.play}>{playing ? 'Pause' : 'Play'}</button>
        <button className="button" disabled={!ready || cursor === length} onClick={playback.next}>Next</button>
        <button className="text-button reset-button" disabled={!ready || (cursor === 0 && !playing)} onClick={playback.reset}>Reset</button>
        <label className="speed-label">Speed<select aria-label="Playback speed" value={delay} onChange={(event) => playback.setDelay(Number(event.target.value))}>
          <option value="1600">0.5×</option><option value="800">1×</option><option value="400">2×</option><option value="200">4×</option>
        </select></label>
      </div>
      <div className="timeline"><input aria-label="Simulation step" type="range" min="0" max={length} value={cursor} disabled={!ready} onChange={(event) => playback.seek(Number(event.target.value))} /><output aria-label="Current step">{cursor} / {length}</output></div>
    </section>
  );
}
