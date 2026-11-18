// 단계 폼: form.steps 안 fieldset.step을 한 번에 하나씩 보여준다.
// JS가 없으면 이 파일은 아무것도 하지 않고, 모든 문항이 보이는 일반 폼으로 동작한다.
(() => {
  const form = document.querySelector("form.steps");
  if (!form) return;
  const steps = [...form.querySelectorAll("fieldset.step")];
  if (steps.length < 2) return;
  const btn = document.querySelector(`button[form="${form.id}"]`);
  const lastLabel = btn ? btn.textContent : "";
  form.noValidate = true; // 숨은 문항 때문에 브라우저 검사가 막히지 않게 단계별로 직접 검사
  form.classList.add("js");

  const top = document.createElement("div");
  top.className = "steps-top";
  top.innerHTML = '<button type="button" class="back" aria-label="이전 질문">←</button><span class="count"></span>';
  const prog = document.createElement("div");
  prog.className = "prog";
  prog.innerHTML = "<i></i>";
  const done = document.createElement("div");
  done.className = "done-list";
  form.prepend(top, prog);
  form.append(done);
  let cur = 0;

  const valid = (s) => {
    const pick = Number(s.dataset.pick || 0);
    if (pick) return s.querySelectorAll("input:checked").length === pick;
    return [...s.querySelectorAll("input")].every((i) => i.checkValidity());
  };
  const answer = (s) => {
    const text = s.querySelector("textarea");
    if (text) return text.value.trim() || "없음";
    const checked = [...s.querySelectorAll("input:checked")].map((i) => i.closest("label").textContent.trim());
    if (checked.length) return checked.join(", ");
    const num = s.querySelector(".num input");
    return num && num.value ? `${num.value} ${num.parentElement.querySelector("em")?.textContent || ""}` : "";
  };

  function show(n, dir) {
    steps.forEach((s, i) => {
      s.classList.toggle("on", i === n);
      s.classList.remove("fwd", "back", "invalid");
    });
    if (dir) steps[n].classList.add(dir);
    cur = n;
    top.querySelector(".count").textContent = `${n + 1} / ${steps.length}`;
    top.querySelector(".back").style.visibility = n ? "visible" : "hidden";
    prog.firstChild.style.width = `${((n + 1) / steps.length) * 100}%`;
    if (btn) btn.textContent = n === steps.length - 1 ? lastLabel : "다음";
    // 답한 항목은 아래에 쌓이고, 누르면 그 질문으로 돌아간다
    done.replaceChildren(...steps.slice(0, n).map((s, i) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "done-item";
      b.innerHTML = "<span></span><b></b>";
      b.firstChild.textContent = s.dataset.name || "";
      b.lastChild.textContent = answer(s);
      b.onclick = () => show(i, "back");
      return b;
    }).reverse());
    const input = steps[n].querySelector(".num input");
    if (input && dir) input.focus({ preventScroll: true });
  }

  function next() {
    const s = steps[cur];
    if (!valid(s)) {
      s.classList.add("invalid");
      s.querySelector(".num input")?.focus();
      return;
    }
    if (cur < steps.length - 1) return show(cur + 1, "fwd");
    const bad = steps.findIndex((x) => !valid(x));
    if (bad >= 0) {
      show(bad, "back");
      steps[bad].classList.add("invalid");
    } else {
      form.submit();
    }
  }

  function limitPicks(s) {
    const pick = Number(s.dataset.pick || 0);
    if (!pick) return;
    const boxes = [...s.querySelectorAll("input[type=checkbox]")];
    const full = boxes.filter((b) => b.checked).length >= pick;
    boxes.forEach((b) => { b.disabled = full && !b.checked; });
  }

  form.addEventListener("submit", (e) => { e.preventDefault(); next(); });
  form.addEventListener("input", (e) => e.target.closest(".step")?.classList.remove("invalid"));
  form.addEventListener("change", (e) => {
    const s = e.target.closest(".step");
    if (!s) return;
    s.classList.remove("invalid");
    limitPicks(s);
    if (e.target.type === "radio" && s === steps[cur]) setTimeout(next, 180); // 고르면 바로 다음
  });
  top.querySelector(".back").onclick = () => cur && show(cur - 1, "back");
  steps.forEach((s) => {
    limitPicks(s);
    s.querySelectorAll(".num input").forEach((i) => i.setAttribute("enterkeyhint", "next"));
  });

  // 서버가 오류로 폼을 다시 보여주면 첫 번째로 틀린 문항부터
  const firstBad = form.querySelector(".error") ? steps.findIndex((x) => !valid(x)) : -1;
  show(firstBad >= 0 ? firstBad : 0);
})();
