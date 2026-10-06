// Loaded only while the GUI is running. No persistent KWin configuration.
const service = "org.local.WhyHere";
const token = "__TOKEN__";
let busy = false;
function identity(w) {
	let desktop = String(w.desktopFileName || "");
	// Only full file paths have an extension to remove; bare IDs are exact.
	if (desktop.startsWith("/")) desktop = desktop.substring(desktop.lastIndexOf("/") + 1).replace(/\.desktop$/, "");
	const resource = String(w.resourceClass || "");
	if (desktop === service || resource === service) return "";
	return desktop ? "desktop:" + desktop : (resource ? "class:" + resource : "");
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
	const snapshot = windows.map(w => ({
		id: String(w.internalId), desktop: String(w.desktopFileName || ""),
		resource: String(w.resourceClass || ""), caption: String(w.caption), pid: Number(w.pid), normal: true
	}));
	callDBus(service, "/Bridge", service, "Exchange", token, JSON.stringify(snapshot), function(reply) {
		busy = false;
		if (!reply) return;
		let commands;
		try { commands = JSON.parse(reply); } catch (e) { return; }
		for (const command of commands) {
			for (const w of workspace.windowList()) {
				if (w.normalWindow && identity(w) && String(w.internalId) === command.id && identity(w) === command.app) {
					w.closeWindow();
				}
			}
		}
	});
}
const timer = new QTimer();
timer.interval = 500;
timer.timeout.connect(exchange);
timer.start();
workspace.windowAdded.connect(exchange);
workspace.windowRemoved.connect(exchange);
exchange();
