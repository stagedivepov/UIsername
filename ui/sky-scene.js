(() => {
  'use strict';
  const canvas = document.getElementById('sky-scene'), ctx = canvas.getContext('2d');
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  let enabled = false, motion = true, frame = 0, width = 0, height = 0, stars = [], meteors = [], last = 0, next = 0;
  function resize() {
    width = innerWidth; height = innerHeight;
    const ratio = Math.min(devicePixelRatio || 1, 1.5);
    canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio);
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    stars = Array.from({length: Math.min(180, Math.max(60, Math.round(width * height / 7500)))}, () => ({
      x: Math.random() * width, y: Math.random() * height, r: .5 + Math.random() * .9,
      alpha: .25 + Math.random() * .6, phase: Math.random() * Math.PI * 2
    }));
    meteors = []; if (enabled) draw(0);
  }
  function draw(time) {
    ctx.clearRect(0, 0, width, height);
    for (const star of stars) {
      ctx.globalAlpha = star.alpha * (.8 + .2 * Math.sin(time / 2000 + star.phase));
      ctx.fillStyle = '#dce9ff'; ctx.beginPath(); ctx.arc(star.x, star.y, star.r, 0, Math.PI * 2); ctx.fill();
    }
    ctx.globalAlpha = 1;
    for (const meteor of meteors) {
      const age = (time - meteor.start) / meteor.duration;
      const x = meteor.x - age * 280, y = meteor.y + age * 150;
      const tail = 85 * Math.sin(Math.PI * age);
      const gradient = ctx.createLinearGradient(x, y, x + tail, y - tail * .54);
      gradient.addColorStop(0, `rgba(231,241,255,${Math.sin(Math.PI * age)})`);
      gradient.addColorStop(1, 'rgba(173,199,255,0)');
      ctx.strokeStyle = gradient; ctx.lineWidth = 1.4; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + tail, y - tail * .54); ctx.stroke();
    }
  }
  function tick(time) {
    frame = 0;
    if (!enabled || !motion || reduced.matches || document.hidden) return;
    if (time - last >= 33) {
      last = time; meteors = meteors.filter(item => time < item.start + item.duration);
      if (time >= next) {
        meteors.push({x: width * (.35 + Math.random() * .6), y: height * Math.random() * .5, start: time, duration: 1200});
        next = time + 3000 + Math.random() * 2500;
      }
      draw(time);
    }
    frame = requestAnimationFrame(tick);
  }
  function sync() {
    cancelAnimationFrame(frame); frame = 0; meteors = [];
    canvas.hidden = !enabled;
    if (!enabled) return;
    draw(0); last = 0; next = performance.now() + 800;
    if (motion && !reduced.matches && !document.hidden) frame = requestAnimationFrame(tick);
  }
  window.SkyScene = {setEnabled(active, animate) {
    if (enabled === active && motion === animate) return;
    enabled = active; motion = animate; sync();
  }};
  addEventListener('resize', resize);
  document.addEventListener('visibilitychange', sync);
  reduced.addEventListener('change', sync);
  resize();
})();
