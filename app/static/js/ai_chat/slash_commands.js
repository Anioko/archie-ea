/**
 * ENT-082: Slash command autocomplete for AI Chat.
 *
 * Listens to #user-input for "/" at position 0, shows matching commands
 * in the #command-hints container, and fills the selected command into
 * the textarea on click.
 */
(function () {
  "use strict";

  let COMMANDS = [
    { cmd: "/help",    args: null,                   desc: "Show available commands" },
    { cmd: "/compare", args: "<solution1> <solution2>", desc: "Compare two solutions" },
    { cmd: "/analyze", args: "<domain>",             desc: "Switch domain and get summary" },
    { cmd: "/arb",     args: "<solution_name>",      desc: "Check ARB readiness for solution" },
    { cmd: "/health",  args: null,                   desc: "Show portfolio health summary" },
    { cmd: "/gaps",    args: "<domain>",             desc: "Run gap analysis for domain" }
  ];

  let input = document.getElementById("user-input");
  let hintsContainer = document.getElementById("command-hints");

  if (!input || !hintsContainer) {
    return;
  }

  /**
   * Return commands whose name starts with the typed prefix.
   */
  function matchCommands(prefix) {
    if (!prefix || prefix === "/") {
      return COMMANDS;
    }
    let lower = prefix.toLowerCase();
    return COMMANDS.filter(function (c) {
      return c.cmd.indexOf(lower) === 0;
    });
  }

  /**
   * Build the hints panel HTML for the given command list.
   */
  function renderHints(commands) {
    if (commands.length === 0) {
      return "";
    }
    let html = '<div class="rounded-md border border-border bg-muted p-2 space-y-1">';
    commands.forEach(function (c) {
      let usage = c.args ? c.cmd + " " + c.args : c.cmd;
      html +=
        '<button type="button" class="slash-hint-btn w-full text-left px-3 py-1.5 rounded-md text-sm hover:bg-accent transition-colors flex items-center gap-2" data-cmd="' +
        c.cmd +
        '">' +
        '<span class="font-mono font-medium text-primary">' + usage + "</span>" +
        '<span class="text-muted-foreground text-xs">' + c.desc + "</span>" +
        "</button>";
    });
    html += "</div>";
    return html;
  }

  /**
   * Show or hide the hints panel based on current input value.
   */
  function updateHints() {
    let val = input.value;

    // Only show hints when "/" is at position 0 and no space yet (still typing the command)
    if (!val.startsWith("/") || (val.indexOf(" ") > 0 && val.indexOf(" ") < val.length)) {
      hintsContainer.innerHTML = "";
      hintsContainer.classList.add("hidden");
      return;
    }

    // Extract the command token (everything before first space, or whole string)
    let spaceIdx = val.indexOf(" ");
    let prefix = spaceIdx === -1 ? val : val.substring(0, spaceIdx);

    let matches = matchCommands(prefix);
    if (matches.length === 0) {
      hintsContainer.innerHTML = "";
      hintsContainer.classList.add("hidden");
      return;
    }

    hintsContainer.innerHTML = renderHints(matches);
    hintsContainer.classList.remove("hidden");

    // Attach click handlers to hint buttons
    let buttons = hintsContainer.querySelectorAll(".slash-hint-btn");
    buttons.forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        let cmd = btn.getAttribute("data-cmd");
        // Find the command definition to check if it needs args
        let cmdDef = COMMANDS.find(function (c) { return c.cmd === cmd; });
        if (cmdDef && cmdDef.args) {
          input.value = cmd + " ";
        } else {
          input.value = cmd;
        }
        hintsContainer.innerHTML = "";
        hintsContainer.classList.add("hidden");
        input.focus();
      });
    });
  }

  // Listen for input changes
  input.addEventListener("input", updateHints);

  // Hide hints on blur (with small delay so click on hint registers)
  input.addEventListener("blur", function () {
    setTimeout(function () {
      hintsContainer.innerHTML = "";
      hintsContainer.classList.add("hidden");
    }, 200);
  });

  // Hide hints on Escape
  input.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      hintsContainer.innerHTML = "";
      hintsContainer.classList.add("hidden");
    }
  });
})();
