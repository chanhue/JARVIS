// 자비스 중앙 비주얼 — 와이어프레임 구체 + 회전 링 + 파티클.
// app.js 가 createReactor(container) 호출해서 setState(stateName) 만 쓰면 됨.

import * as THREE from "three";

const STATE_COLORS = {
  standby: 0x00d4ff,        // 시안 — 기본
  listening: 0x9af0ff,      // 밝은 시안
  thinking: 0xffb347,       // 앰버
  speaking: 0x6effb3,       // 그린
  error: 0xff5d6c,          // 레드
  "needs-setup": 0x6f9bbf,  // 회색 시안
};

const STATE_PULSE = {
  standby: 1.0,
  listening: 3.0,
  thinking: 2.0,
  speaking: 4.5,
  error: 1.5,
  "needs-setup": 0.6,
};

export function createReactor(container) {
  const width = container.clientWidth || 400;
  const height = container.clientHeight || 400;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
  // 카메라를 충분히 뒤로 — 바깥 링 + 파티클까지 다 화면에 들어오도록.
  // FOV 45°, 카메라 z=7.5 → z=0 평면에서 보이는 반높이 ≈ 3.1 (최외곽 파티클 r≈2.8 + 여유)
  camera.position.z = 7.5;

  const renderer = new THREE.WebGLRenderer({
    alpha: true,
    antialias: true,
  });
  renderer.setSize(width, height);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  container.appendChild(renderer.domElement);

  const root = new THREE.Group();
  scene.add(root);

  // 각 vertex 를 반경 방향으로 무작위로 ±amount 만큼 밀어내 격자를 깬다.
  // 영화 J.A.R.V.I.S. 의 와이어프레임처럼 "균일한 측지 돔" 느낌을 줄여줌.
  function perturbSphere(geom, amount) {
    const pos = geom.attributes.position;
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i);
      const y = pos.getY(i);
      const z = pos.getZ(i);
      const r = Math.sqrt(x * x + y * y + z * z);
      if (r < 1e-4) continue;
      const scale = 1 + (Math.random() - 0.5) * 2 * amount;
      pos.setXYZ(i, x * scale, y * scale, z * scale);
    }
    pos.needsUpdate = true;
    geom.computeVertexNormals();
  }

  // ── 와이어프레임 구체 (메인) — 무작위 변형 ────────────────
  const sphereMat = new THREE.MeshBasicMaterial({
    color: STATE_COLORS.standby,
    wireframe: true,
    transparent: true,
    opacity: 0.55,
  });
  const sphereGeom = new THREE.IcosahedronGeometry(1.55, 4);
  perturbSphere(sphereGeom, 0.15);
  const sphere = new THREE.Mesh(sphereGeom, sphereMat);
  root.add(sphere);

  // ── 살짝 큰 외곽 와이어 구체 — 깊이감 + 다른 변형 ─────────
  const outerMat = new THREE.MeshBasicMaterial({
    color: STATE_COLORS.standby,
    wireframe: true,
    transparent: true,
    opacity: 0.2,
  });
  const outerGeom = new THREE.IcosahedronGeometry(1.95, 3);
  perturbSphere(outerGeom, 0.22);
  const outer = new THREE.Mesh(outerGeom, outerMat);
  root.add(outer);

  // ── 안쪽 코어 (작고 또렷한 점) ────────────────────────────
  const coreMat = new THREE.MeshBasicMaterial({
    color: STATE_COLORS.standby,
    transparent: true,
    opacity: 0.98,
  });
  const core = new THREE.Mesh(
    new THREE.SphereGeometry(0.18, 24, 24),
    coreMat
  );
  root.add(core);

  // 코어 둘레 글로우
  const haloMat = new THREE.MeshBasicMaterial({
    color: STATE_COLORS.standby,
    transparent: true,
    opacity: 0.22,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const halo = new THREE.Mesh(
    new THREE.SphereGeometry(0.42, 24, 24),
    haloMat
  );
  root.add(halo);

  // ── 회전 링 3개 (서로 다른 축/속도) ──────────────────────
  const ringConfigs = [
    {
      radius: 2.05,
      tube: 0.012,
      rot: [Math.PI / 2, 0, 0],
      speed: [0.003, 0.0, 0.001],
      opacity: 0.85,
    },
    {
      radius: 2.18,
      tube: 0.008,
      rot: [0, Math.PI / 3, Math.PI / 4],
      speed: [0.001, 0.005, 0.0],
      opacity: 0.7,
    },
    {
      radius: 2.32,
      tube: 0.006,
      rot: [Math.PI / 4, 0, Math.PI / 2],
      speed: [0.0, 0.0024, 0.003],
      opacity: 0.55,
    },
  ];
  const rings = [];
  const ringMats = [];
  for (const cfg of ringConfigs) {
    const mat = new THREE.MeshBasicMaterial({
      color: STATE_COLORS.standby,
      transparent: true,
      opacity: cfg.opacity,
    });
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(cfg.radius, cfg.tube, 16, 120),
      mat
    );
    ring.rotation.set(...cfg.rot);
    ring.userData.speed = cfg.speed;
    ringMats.push(mat);
    rings.push(ring);
    root.add(ring);
  }

  // ── 파티클 (구 셸 내부에 랜덤 분포) ─────────────────────
  const PARTICLE_COUNT = 900;
  const positions = new Float32Array(PARTICLE_COUNT * 3);
  for (let i = 0; i < PARTICLE_COUNT; i++) {
    const r = 1.8 + Math.random() * 1.0;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
    positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
    positions[i * 3 + 2] = r * Math.cos(phi);
  }
  const particleGeom = new THREE.BufferGeometry();
  particleGeom.setAttribute(
    "position",
    new THREE.BufferAttribute(positions, 3)
  );
  const particleMat = new THREE.PointsMaterial({
    color: STATE_COLORS.standby,
    size: 0.022,
    transparent: true,
    opacity: 0.85,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const particles = new THREE.Points(particleGeom, particleMat);
  root.add(particles);

  // ── 색상 보간 상태 ────────────────────────────────────
  const currentColor = new THREE.Color(STATE_COLORS.standby);
  const targetColor = new THREE.Color(STATE_COLORS.standby);
  const whiteColor = new THREE.Color(0xffffff);

  let pulseSpeed = STATE_PULSE.standby;
  let elapsed = 0;

  function setState(state) {
    const hex = STATE_COLORS[state] ?? STATE_COLORS.standby;
    targetColor.setHex(hex);
    pulseSpeed = STATE_PULSE[state] ?? 1.0;
  }

  // ── 애니메이션 루프 ────────────────────────────────────
  function animate() {
    requestAnimationFrame(animate);
    elapsed += 0.016;

    // 색상 lerp — 부드러운 전환
    currentColor.lerp(targetColor, 0.06);
    sphereMat.color.copy(currentColor);
    outerMat.color.copy(currentColor);
    particleMat.color.copy(currentColor);
    haloMat.color.copy(currentColor);
    for (const mat of ringMats) mat.color.copy(currentColor);
    // 코어는 약간 더 밝게 (현재색 + 흰색 살짝)
    coreMat.color.copy(currentColor).lerp(whiteColor, 0.35);

    // 구체 자전
    sphere.rotation.y += 0.0025;
    sphere.rotation.x += 0.001;
    outer.rotation.y -= 0.0018;
    outer.rotation.z += 0.0008;

    // 전체 그룹 살짝 회전 (깊이 느낌)
    root.rotation.y += 0.0006;

    // 링 각자 다른 속도
    for (const ring of rings) {
      ring.rotation.x += ring.userData.speed[0];
      ring.rotation.y += ring.userData.speed[1];
      ring.rotation.z += ring.userData.speed[2];
    }

    // 파티클 회전
    particles.rotation.y -= 0.0006;
    particles.rotation.x += 0.0003;

    // 코어 / 헤일로는 부풀지 않음 (가만히).
    // 테두리(외곽 구체 + 링 + 파티클)는 사인파로 같이 들숨/날숨 — 같은 위상이라
    // 링끼리 안 부딪힘. 외곽 구체와 파티클은 위상이 살짝 어긋나서 레이어가
    // 따로 호흡하는 인상.
    const breathT = elapsed * pulseSpeed * 0.4;
    const breath = Math.sin(breathT);

    rings.forEach((ring, idx) => {
      const amp = 0.025 + idx * 0.015;
      ring.scale.setScalar(1.0 + amp * breath);
    });
    outer.scale.setScalar(1.0 + 0.06 * Math.sin(breathT - 0.4));
    particles.scale.setScalar(1.0 + 0.05 * Math.sin(breathT + 0.3));

    renderer.render(scene, camera);
  }
  animate();

  // ── 리사이즈 ─────────────────────────────────────────
  function onResize() {
    const w = container.clientWidth;
    const h = container.clientHeight;
    if (!w || !h) return;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
  }
  window.addEventListener("resize", onResize);
  const ro = new ResizeObserver(onResize);
  ro.observe(container);

  return { setState };
}
