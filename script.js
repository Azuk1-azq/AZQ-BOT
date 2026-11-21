const commandTabs = document.getElementById("commandTabs").children;
const commandItems = document.getElementById("commandList").children;
const faqSearch = document.getElementById("faqSearch");
const faqItems = document.getElementById("faq").getElementsByTagName("details");
const faqEmpty = document.getElementById("faqEmpty");
const copyNotice = document.getElementById("copyNotice");
let noticeTimer;

function showNotice(message) {
  copyNotice.textContent = message;
  copyNotice.classList.add("show");
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(function () {
    copyNotice.classList.remove("show");
  }, 1800);
}

for (let i = 0; i < commandTabs.length; i++) {
  commandTabs[i].onclick = function () {
    for (let j = 0; j < commandTabs.length; j++) {
      commandTabs[j].classList.remove("on");
    }
    commandTabs[i].classList.add("on");
    const role = commandTabs[i].dataset.role;
    for (let j = 0; j < commandItems.length; j++) {
      commandItems[j].hidden = role !== "all" && commandItems[j].dataset.role !== role;
    }
  };
}

for (let i = 0; i < commandItems.length; i++) {
  commandItems[i].onclick = function () {
    const command = commandItems[i].dataset.copy;
    navigator.clipboard.writeText(command).then(function () {
      showNotice(`${command} をコピーしました`);
    }, function () {
      showNotice("コピーできませんでした");
    });
  };
}

faqSearch.oninput = function () {
  const word = faqSearch.value.trim().toLowerCase();
  let shown = 0;
  for (let i = 0; i < faqItems.length; i++) {
    const hit = faqItems[i].textContent.toLowerCase().includes(word);
    faqItems[i].hidden = !hit;
    if (hit) {
      shown++;
    }
  }
  faqEmpty.hidden = shown > 0;
};
