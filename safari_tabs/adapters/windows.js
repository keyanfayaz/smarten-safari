// JXA uses Safari's Apple Events dictionary, not JavaScript inside web pages.
function run() {
    const safari = Application("com.apple.Safari");
    const result = {scopes: [], tabs: []};
    if (!safari.running()) return JSON.stringify(result);
    for (const window of safari.windows()) {
        const id = String(window.id());
        const titles = window.tabs.name();
        const urls = window.tabs.url();
        if (titles.length !== urls.length) {
            throw new Error("Safari tabs changed during collection; retry the query.");
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
