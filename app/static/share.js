// 자랑하기: 폰 공유 창으로 카드 이미지만 보낸다(토큰이 든 주소는 보내지 않음).
// 공유가 안 되는 곳(카톡 안 브라우저·PC)은 카드를 펼쳐 길게 눌러 저장하게 한다. JS가 없으면 링크가 PNG를 연다.
(() => {
  const a = document.querySelector("a.share");
  if (!a) return;
  const fallback = document.querySelector(".share-fallback");
  const open = () => { if (fallback) { fallback.hidden = false; fallback.scrollIntoView({ behavior: "smooth", block: "center" }); } };
  a.addEventListener("click", async (e) => {
    e.preventDefault();
    try {
      const blob = await (await fetch(a.href)).blob();
      const file = new File([blob], "watchme.png", { type: "image/png" });
      if (!navigator.canShare?.({ files: [file] })) return open();
      await navigator.share({ files: [file], text: a.dataset.text });
    } catch (err) {
      if (err?.name !== "AbortError") open(); // 공유 창을 닫은 건 실패가 아님
    }
  });
})();
