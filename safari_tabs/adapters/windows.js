// JXA uses Safari's Apple Events dictionary, not JavaScript inside web pages.
function collect(safari) {
    const result = {scopes: [], tabs: []};
    if (!safari.running()) return JSON.stringify(result);
    for (const window of safari.windows()) {
        const id = String(window.id());
        const titles = window.tabs.name();
        const urls = window.tabs.url();
        if (titles.length !== urls.length) {
            return null;
        }
        result.scopes.push({id: id, name: "Window " + id, kind: "window"});
        for (let index = 0; index < titles.length; index++) {
            result.tabs.push({
                id: id + ":" + (index + 1), scope_id: id,
                title: titles[index] ?? null, url: urls[index] ?? null,
                position: index + 1
            });
        }
    }
    return JSON.stringify(result);
}

function run() {
    const safari = Application("com.apple.Safari");
    let previous = null;
    // Equal counts do not detect reordering or navigation between title/URL reads.
    for (let attempt = 0; attempt < 3; attempt++) {
        const current = collect(safari);
        if (current !== null && current === previous) return current;
        previous = current;
    }
    throw new Error("Safari tabs changed during collection; retry the query.");
}
