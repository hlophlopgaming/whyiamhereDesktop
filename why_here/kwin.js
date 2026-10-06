// Loaded only while the GUI is running. No persistent KWin configuration.
const service = "org.local.WhyHere";
const token = "__TOKEN__";
let busy = false;
let blocked = {};
function identity(w) {
	let desktop = String(w.desktopFileName || "");
	// Only full file paths have an extension to remove; bare IDs are exact.
	if (desktop.startsWith("/")) desktop = desktop.substring(desktop.lastIndexOf("/") + 1).replace(/\.desktop$/, "");
	const resource = String(w.resourceClass || "");
	if (desktop === service || resource === service) return "";
	return desktop ? "desktop:" + desktop : (resource ? "class:" + resource : "");
}
function windowById(id) {
	return workspace.windowList().find(w => String(w.internalId) === id);
}
function promptWindow() {
	return workspace.windowList().find(w => {
		const caption = String(w.caption);
		return String(w.desktopFileName) === service &&
			(caption.indexOf("Зачем я здесь? — ") === 0 || caption.indexOf("Why am I here? — ") === 0) &&
			caption.indexOf("напоминание") < 0 && caption.indexOf("reminder") < 0;
	});
}
function focusPrompt() {
	if (!Object.keys(blocked).length) return;
	const prompt = promptWindow();
	if (!prompt) return;
	prompt.minimized = false;
	prompt.keepAbove = true;
	workspace.raiseWindow(prompt);
	workspace.activeWindow = prompt;
}
function apply(commands) {
	const next = {};
	for (const command of commands) {
		const w = windowById(command.id);
		if (!w || !w.normalWindow || identity(w) !== command.app) continue;
		if (command.action === "block") {
			next[command.id] = blocked[command.id] || {minimized: w.minimized};
			w.minimized = true;
		} else {
			w.closeWindow();
		}
	}
	for (const id of Object.keys(blocked)) {
		if (next[id]) continue;
		const w = windowById(id);
		if (w) w.minimized = blocked[id].minimized;
	}
	blocked = next;
	focusPrompt();
}
function exchange() {
	if (busy) return;
	busy = true;
	for (const w of workspace.windowList()) {
		if (String(w.desktopFileName) === service && (String(w.caption).indexOf("Зачем я здесь? — напоминание") === 0 || String(w.caption).indexOf("Why am I here? — reminder") === 0)) {
			w.keepAbove = true;
			w.skipTaskbar = true;
			w.skipPager = true;
		}
	}
	const windows = workspace.windowList().filter(w => w.normalWindow && identity(w));
	const prompt = promptWindow();
	const snapshot = windows.map(w => ({
		id: String(w.internalId), desktop: String(w.desktopFileName || ""),
		resource: String(w.resourceClass || ""), caption: String(w.caption), pid: Number(w.pid), normal: true,
		minimized: Boolean(w.minimized), promptActive: Boolean(prompt && workspace.activeWindow === prompt)
	}));
	callDBus(service, "/Bridge", service, "Exchange", token, JSON.stringify(snapshot), function(reply) {
		busy = false;
		if (!reply) return;
		let commands;
		try { commands = JSON.parse(reply); } catch (e) { return; }
		apply(commands);
	});
}
const timer = new QTimer();
timer.interval = 500;
timer.timeout.connect(exchange);
timer.start();
workspace.windowAdded.connect(exchange);
workspace.windowRemoved.connect(exchange);
workspace.windowActivated.connect(function(w) {
	if (w && blocked[String(w.internalId)]) w.minimized = true;
	const prompt = promptWindow();
	if (w && prompt && w !== prompt) focusPrompt();
});
exchange();
