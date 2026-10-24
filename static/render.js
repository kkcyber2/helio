// Renderer, camera and the drag-to-rotate rig. Kept apart from the product
// geometry so the watch model has no opinion about how it is viewed.

(() => {
  const canvas = document.getElementById("stage");
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputEncoding = THREE.sRGBEncoding;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 100);

  // Three-point studio light: key from upper left, fill opposite, and a hard
  // specular kicker that gives the case its edge highlight.
  const key = new THREE.DirectionalLight(0xffffff, 2.6);
  key.position.set(-2.2, 3.4, 2.4);
  scene.add(key);

  const fill = new THREE.DirectionalLight(0xbcd4e8, 0.9);
  fill.position.set(3.0, 0.6, 1.4);
  scene.add(fill);

  const kicker = new THREE.DirectionalLight(0xffffff, 1.8);
  kicker.position.set(1.4, 1.8, -3.2);
  scene.add(kicker);

  scene.add(new THREE.HemisphereLight(0xdfe8f0, 0x2a2c30, 0.55));

  // A soft ground plane catching a contact shadow makes the object sit in space
  // rather than float.
  const floor = new THREE.Mesh(
    new THREE.CircleGeometry(6, 48),
    new THREE.MeshStandardMaterial({ color: 0x101214, roughness: 0.95, metalness: 0 })
  );
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = -1.15;
  scene.add(floor);

  const rig = {
    azimuth: 0.42,
    elevation: 0.44,
    radius: 5.4,
    dAzimuth: 0.42,
    dElevation: 0.44,
    dRadius: 5.4,
    dragging: false,
    lastX: 0,
    lastY: 0,
  };

  function place() {
    camera.position.set(
      Math.sin(rig.azimuth) * Math.cos(rig.elevation) * rig.radius,
      Math.sin(rig.elevation) * rig.radius,
      Math.cos(rig.azimuth) * Math.cos(rig.elevation) * rig.radius
    );
    camera.lookAt(0, 0.16, 0);
  }

  function resize() {
    const w = canvas.clientWidth || canvas.parentElement.clientWidth;
    const h = canvas.clientHeight || canvas.parentElement.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }

  canvas.addEventListener("pointerdown", (e) => {
    rig.dragging = true;
    rig.lastX = e.clientX;
    rig.lastY = e.clientY;
    canvas.setPointerCapture(e.pointerId);
    canvas.style.cursor = "grabbing";
  });

  canvas.addEventListener("pointermove", (e) => {
    if (!rig.dragging) return;
    rig.dAzimuth -= (e.clientX - rig.lastX) * 0.008;
    rig.dElevation = Math.max(-0.15, Math.min(1.2, rig.dElevation + (e.clientY - rig.lastY) * 0.006));
    rig.lastX = e.clientX;
    rig.lastY = e.clientY;
  });

  const release = (e) => {
    rig.dragging = false;
    canvas.style.cursor = "grab";
    if (e.pointerId !== undefined && canvas.hasPointerCapture?.(e.pointerId)) {
      canvas.releasePointerCapture(e.pointerId);
    }
  };
  canvas.addEventListener("pointerup", release);
  canvas.addEventListener("pointercancel", release);

  canvas.addEventListener(
    "wheel",
    (e) => {
      e.preventDefault();
      rig.dRadius = Math.max(3.4, Math.min(8.0, rig.dRadius + e.deltaY * 0.0022));
    },
    { passive: false }
  );

  window.addEventListener("resize", resize);

  const clock = new THREE.Clock();
  function loop() {
    requestAnimationFrame(loop);
    const dt = Math.min(clock.getDelta(), 0.05);
    if (window.__spin) rig.dAzimuth += dt * 0.55;  // set by the Spin button

    // Critically-damped-ish easing: fast enough to feel responsive, slow enough
    // to read as motion rather than a jump.
    const k = 1 - Math.pow(0.001, dt);
    rig.azimuth += (rig.dAzimuth - rig.azimuth) * k;
    rig.elevation += (rig.dElevation - rig.elevation) * k;
    rig.radius += (rig.dRadius - rig.radius) * k;

    place();
    renderer.render(scene, camera);
  }

  resize();
  place();
  loop();

  window.__scene = scene;
  window.__camera = camera;
  window.__renderer = renderer;
})();
