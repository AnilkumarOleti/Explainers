# Explainers

**Read them here: https://anilkumaroleti.github.io/Explainers/**

Each page explains one idea with a picture you can play with. There are 70 so far, in seven groups: analytics and data science, AI and technology, body and health, brain and mind, big ideas, world and history, and screen and sport.

Nothing to install. Every page opens in any browser, on a phone or a laptop, and has its own address you can share, for example https://anilkumaroleti.github.io/Explainers/why-cant-you-tickle-yourself/.

These pages are for understanding. The health pages are not medical advice.

The analytics and data science group includes the eleven picture pages from the [DS/ML Learning Handbook](https://anilkumaroleti.github.io/ds-ml-handbook/), a separate site with 77 concept pages. Each of those pages links to its full topic there.

## What is in this repository

- `index.html` is the home page: a question to start with, then every page grouped by subject.
- Each explainer has its own folder, named after its address. Inside are `index.html` (the page), `card.jpg` (the picture shown when the link is shared) and `thumb.webp` (the small picture on the home page).
- `tools/catalog.json` lists every page: its group, address, title and the line shown under it on the home page. The home page is built from this file.
- `tools/build.py` builds the pages and the home page. `tools/shots.py` makes the pictures.
- `tools/dashboard.py` turns a dashboard into a single page that `tools/build.py` can take. World hunger and The AI model race were made this way. They draw their charts with d3, which is kept in `assets/`.

## Adding or updating a page

1. Save the page into a folder of its own as `index.html`, inside one parent folder, for example `saved/my-page/index.html`.
   A dashboard is several documents, not one page: export them and run `python3 tools/dashboard.py <export-folder> <csv-folder> saved/my-page` first. Its data must be attached files; a dashboard that runs live queries cannot be made public this way.
2. Add an entry for it to `tools/catalog.json`, in the group it belongs to. It needs a `slug` (the address), a `title` that matches the page's own title, and a `blurb`. Add `ask` to put its question in the rotation at the top of the home page.
3. Run `python3 tools/build.py saved`. Pages that are not in `saved` are left as they are.
4. Run `python3 tools/shots.py` to make pictures for the pages that have none.
5. Publish: `git push origin main main:gh-pages`.

The site is served from the `gh-pages` branch, which is kept identical to `main`.

To take a page down, delete its folder and its entry in `tools/catalog.json`, run `python3 tools/build.py`, and publish.

Each page is built from a saved copy and gets only a document head (title, description, link-preview tags) and one link back to the home page. Edits made directly to a page's `index.html` are overwritten the next time that page is rebuilt.
