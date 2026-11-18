// 랜딩 스토리: main.story 안 section.scene을 한 번에 하나씩 보여 주고 자동으로 넘긴다.
// JS가 없으면 이 파일은 아무것도 하지 않고, 장면이 위에서 아래로 쌓여 보인다.
(() => {
  const story = document.querySelector("main.story");
  if (!story) return;
  const scenes = [...story.querySelectorAll(".scene")];
  const segs = [...story.querySelectorAll(".seg")];
  const fills = segs.map((s) => s.querySelector("b"));
  const DUR = [3000, 3600, 3800, 4600]; // 마지막 장면은 멈춤
  const auto = !matchMedia("(prefers-reduced-motion: reduce)").matches;
  const last = scenes.length - 1;
  let cur = 0, elapsed = 0;
  story.classList.add("js");

  function go(n) {
    cur = Math.max(0, Math.min(n, last));
    elapsed = 0;
    scenes.forEach((s, i) => {
      s.classList.toggle("cur", i === cur);
      s.classList.toggle("prev", i < cur);
      s.setAttribute("aria-hidden", i === cur ? "false" : "true");
    });
    fills.forEach((b, i) => { b.style.width = i < cur || cur === last ? "100%" : "0"; });
    story.classList.toggle("lt", scenes[cur].classList.contains("g"));
    story.classList.toggle("at-end", cur === last);
  }

  segs.forEach((s, i) => { s.onclick = () => go(i); });
  story.querySelector(".tap").onclick = () => go(cur + 1);

  const STEP = 50;
  if (auto) setInterval(() => {
    if (document.hidden || cur === last) return;
    elapsed += STEP;
    const d = DUR[cur] || DUR[DUR.length - 1];
    fills[cur].style.width = `${Math.min(1, elapsed / d) * 100}%`;
    if (elapsed >= d) go(cur + 1);
  }, STEP);
  go(0);
})();
