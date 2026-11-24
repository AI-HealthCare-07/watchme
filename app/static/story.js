// 랜딩 스토리: main.story 안 section.scene을 한 번에 하나씩 보여 주고 자동으로 넘긴다.
// JS가 없으면 이 파일은 아무것도 하지 않고, 장면이 위에서 아래로 쌓여 보인다.
(() => {
  const story = document.querySelector("main.story");
  if (!story) return;
  const scenes = [...story.querySelectorAll(".scene")];
  const segs = [...story.querySelectorAll(".seg")];
  const fills = segs.map((s) => s.querySelector("b"));
  const DUR = [3600, 3600, 3800, 5000]; // 마지막 장면은 멈춤
  const auto = !matchMedia("(prefers-reduced-motion: reduce)").matches;
  const last = scenes.length - 1;
  let cur = 0, elapsed = 0, held = false;
  story.classList.add("js");

  function go(n) {
    cur = Math.max(0, Math.min(n, last));
    elapsed = 0;
    scenes.forEach((s, i) => {
      s.classList.toggle("cur", i === cur);
      s.classList.toggle("prev", i < cur);
      s.inert = i !== cur; // 안 보이는 장면은 탭 이동·스크린리더에서 빠진다
    });
    fills.forEach((b, i) => { b.style.width = i < cur || cur === last ? "100%" : "0"; });
    story.classList.toggle("lt", scenes[cur].classList.contains("g"));
    if (auto) counts(scenes[cur]);
  }

  // 숫자가 0부터 올라간다(게이지가 차오르는 것과 같이). 움직임 줄이기면 처음부터 최종 숫자.
  function countUp(el, to, show, delay) {
    const run = (el.run = (el.run || 0) + 1);
    const t0 = performance.now() + delay;
    const tick = (t) => {
      if (el.run !== run) return; // 장면을 다시 열면 새로 시작
      const p = Math.min(1, Math.max(0, (t - t0) / 1200));
      el.textContent = show(Math.round(to * (1 - (1 - p) ** 3)));
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }
  function counts(scene) {
    scene.querySelectorAll("[data-count]").forEach((el) =>
      countUp(el, +el.dataset.count, (n) => n.toLocaleString("ko-KR"), el.closest(".gauge") ? 400 : 300));
  }

  segs.forEach((s, i) => { s.onclick = () => go(i); });
  // 장면을 누르면 다음 (링크·버튼·접기는 제외). 스크롤은 click이 아니라 넘어가지 않는다.
  scenes.forEach((s) => s.addEventListener("click", (e) => {
    if (cur !== last && !e.target.closest("a, button, summary, details")) go(cur + 1);
  }));
  // 누르고 있는 동안은 멈춤(스토리처럼)
  story.addEventListener("pointerdown", () => { held = true; });
  addEventListener("pointerup", () => { held = false; });
  addEventListener("pointercancel", () => { held = false; });

  const STEP = 50;
  if (auto) setInterval(() => {
    // 탭이 숨겨졌거나, 누르고 있거나, 키보드로 장면 안을 보고 있으면 멈춤
    if (document.hidden || held || cur === last || story.querySelector(":focus-visible")) return;
    elapsed += STEP;
    const d = DUR[cur] || DUR[DUR.length - 1];
    fills[cur].style.width = `${Math.min(1, elapsed / d) * 100}%`;
    if (elapsed >= d) go(cur + 1);
  }, STEP);
  go(0);
})();
