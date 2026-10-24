// The watch, built from primitives. No model files, no textures: every surface
// is geometry with a physical material, so changing an option is a material or
// scale swap rather than an image swap.

const WATCH = (() => {
  const D2R = Math.PI / 180;

  function makeWatch(scene) {
    const group = new THREE.Group();
    scene.add(group);

    // --- case: a lathe profile, so the bezel has an actual chamfer -----------
    const profile = [];
    const R = 1.0;      // case radius
    profile.push(new THREE.Vector2(0.0, -0.052));
    profile.push(new THREE.Vector2(R * 0.86, -0.052));
    profile.push(new THREE.Vector2(R * 0.97, -0.036));
    profile.push(new THREE.Vector2(R, 0.0));
    profile.push(new THREE.Vector2(R * 0.985, 0.030));
    profile.push(new THREE.Vector2(R * 0.93, 0.046));   // bezel chamfer
    profile.push(new THREE.Vector2(0.0, 0.046));
    const caseGeo = new THREE.LatheGeometry(profile, 96);
    const caseMat = new THREE.MeshPhysicalMaterial({
      color: 0xb9bec4, metalness: 0.92, roughness: 0.28, clearcoat: 0.4, clearcoatRoughness: 0.3,
    });
    const caseMesh = new THREE.Mesh(caseGeo, caseMat);
    group.add(caseMesh);

    // --- crystal -------------------------------------------------------------
    const crystalMat = new THREE.MeshPhysicalMaterial({
      color: 0xffffff, metalness: 0, roughness: 0.03, transmission: 0.92,
      thickness: 0.10, ior: 1.5, transparent: true, opacity: 0.5,
    });
    const crystal = new THREE.Mesh(new THREE.CylinderGeometry(R * 0.90, R * 0.90, 0.012, 64), crystalMat);
    crystal.position.y = 0.050;
    group.add(crystal);

    // --- dial ---------------------------------------------------------------
    const dialMat = new THREE.MeshStandardMaterial({ color: 0xe8e2d4, roughness: 0.7, metalness: 0.05 });
    const dial = new THREE.Mesh(new THREE.CylinderGeometry(R * 0.855, R * 0.855, 0.010, 64), dialMat);
    dial.position.y = 0.040;
    group.add(dial);

    // Indices: twelve thin boxes, laid out by angle. A real dial, not a texture.
    const indexMat = new THREE.MeshStandardMaterial({ color: 0x2b2d31, metalness: 0.5, roughness: 0.4 });
    const indices = new THREE.Group();
    for (let i = 0; i < 12; i++) {
      const a = i * 30 * D2R;
      const isQuarter = i % 3 === 0;
      const h = isQuarter ? 0.15 : 0.09;
      const geo = new THREE.BoxGeometry(0.022, 0.004, h);
      const m = new THREE.Mesh(geo, indexMat);
      const r = R * 0.855 - h / 2 - 0.035;
      m.position.set(Math.sin(a) * r, 0.047, Math.cos(a) * r);
      m.rotation.y = a;
      indices.add(m);
    }
    group.add(indices);

    // Hands, frozen at a considered time rather than a random one.
    const handMat = new THREE.MeshStandardMaterial({ color: 0x1b1c1f, metalness: 0.6, roughness: 0.35 });
    const hourHand = new THREE.Mesh(new THREE.BoxGeometry(0.030, 0.006, 0.42), handMat);
    hourHand.position.set(0.07, 0.052, 0.14);
    hourHand.rotation.y = -38 * D2R;
    group.add(hourHand);
    const minHand = new THREE.Mesh(new THREE.BoxGeometry(0.020, 0.006, 0.60), handMat);
    minHand.position.set(-0.10, 0.054, 0.16);
    minHand.rotation.y = 128 * D2R;
    group.add(minHand);
    const secHand = new THREE.Mesh(new THREE.BoxGeometry(0.008, 0.004, 0.66),
      new THREE.MeshStandardMaterial({ color: 0xa85a3a, metalness: 0.4, roughness: 0.5 }));
    secHand.position.set(0.0, 0.056, -0.02);
    secHand.rotation.y = 62 * D2R;
    group.add(secHand);
    const centre = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, 0.014, 24), handMat);
    centre.position.y = 0.056;
    group.add(centre);

    // --- lugs and strap ------------------------------------------------------
    const lugMat = caseMat;
    for (const side of [-1, 1]) {
      for (const off of [-1, 1]) {
        const lug = new THREE.Mesh(new THREE.BoxGeometry(0.10, 0.055, 0.10), lugMat);
        lug.position.set(off * 0.66, -0.005, side * (R * 0.96));
        group.add(lug);
      }
    }

    const strapMat = new THREE.MeshStandardMaterial({ color: 0x6b4a2f, roughness: 0.85, metalness: 0.02 });
    const strapMeshes = [];
    for (const side of [-1, 1]) {
      // A gentle curve, made of segments, so the strap hangs rather than sticks out.
      const segs = 14;
      for (let i = 0; i < segs; i++) {
        const t = i / (segs - 1);
        const len = 0.26;
        const geo = new THREE.BoxGeometry(0.52 - t * 0.05, 0.030, len * 0.92);
        const m = new THREE.Mesh(geo, strapMat);
        const drop = Math.pow(t, 1.7) * 0.62;
        m.position.set(0, -0.012 - drop, side * (R * 1.05 + t * 1.0));
        m.rotation.x = side * (t * 0.55);
        strapMeshes.push(m);
        group.add(m);
      }
    }

    return { group, caseMesh, caseMat, dialMat, strapMat, crystal };
  }

  return { makeWatch };
})();
