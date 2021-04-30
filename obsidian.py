import os
import re
import sublime
import sublime_plugin

def log(msg: str):
    print("obsidian-notes: " + str(msg))

def collect_links(file):
    pattern = re.compile('\\[\\[.*?\\]\\]')

    links = []
    for line in file.readlines():
        matches = pattern.findall(line)
        for match in matches:
            links.append(match[2:-2])
    return links

def note_name_from_link(link: str) -> str:
    # Link format is [[Name#Heading|Alias]]
    # ignore the heading for now
    location = link.split('|')[0]
    return location.split('#')[0]

def path_to_note(view: sublime.View, note_name: str) -> str:
    # Search for a note with that name in the window's folders
    # Return the first one we find.
    for folder in view.window().folders():
        for (root, dirs, files) in os.walk(folder):
            for file in files:
                if file.startswith(note_name):
                    path = os.path.join(root, file)
                    return path
    return None

def file_extension(path: str) -> str:
    tokens = path.split('.')
    if len(tokens) == 1:
        return None
    else:
        return tokens[-1]

# Opens [[Links]] to notes
class ObsidianOpenNoteCommand(sublime_plugin.TextCommand):

    def is_enabled(self, event=None):
        # The command is only enabled within [[ ]]
        layout_pos = self.view.window_to_layout((event['x'], event['y']))
        text_pos = self.view.layout_to_text(layout_pos)
        return self.view.match_selector(text_pos, 'meta.brackets markup.underline.link') or self.view.match_selector(text_pos, 'meta.brackets markup.raw.block')

    def want_event(self):
        return True

    def run(self, edit, event=None):
        layout_pos = self.view.window_to_layout((event['x'], event['y']))
        text_pos = self.view.layout_to_text(layout_pos)
        region = self.view.extract_scope(text_pos)
        link = self.view.substr(region)

        note_name = note_name_from_link(link)

        log('open ' + note_name)

        # Search for a note with that name in the window's folders
        # open the first one we find.
        path = path_to_note(self.view, note_name)
        if path:
            self.view.window().open_file(path)

class Note:

    def __init__(self, path: str, links: [str]):
        self.path = path
        self.links = links
        pass

class Index:

    def __init__(self):
        # set of open folders
        self.folders = set()
        # map from names to Notes
        self.notes = {}

    def update(self, new_folders: [str]):
        new_set = set(new_folders)

        # if the set of folders has changed, just re-index everything
        if len(new_set ^ self.folders) > 0:
            log("update index")
            self.folders = new_set
            self.notes = {}
            for folder in new_set:
                for root, dirs, files in os.walk(folder):
                    for file in files:
                        extension = file[-3:]
                        if extension == '.md' or extension == '.MD':
                            name = file[:-3]
                            path = root + '/' + file
                            links = []
                            with open(path, 'r', encoding='utf-8') as f:
                                links = collect_links(f)
                            self.notes[name] = Note(path, links)

    # return the links for a note
    def links(self, note: Note) -> [str]:
        if note in self.notes:
            return self.notes[note].links
        return []

    # return the backlinks for a note (doesn't actually do that yet)
    def backlinks(self, note: Note) -> [str]:
        if note in self.notes:
            return self.notes[note].links
        return []

class ObsidianListener(sublime_plugin.EventListener):

    def __init__(self):
        # Map from windows ids to indexes
        # Each window is associated with one index
        self.indexes = {}

    # Utilities

    def index_for_view(self, view: sublime.View) -> Index:
        key = view.window().id()

        if key not in self.indexes:
            index = Index()
            self.indexes[key] = index

        return self.indexes[key]

    # sublime_plugin.EventListener Overrides

    # Plugin activation handler
    def on_activated(self, view):
        # Update the index associated with the view's window
        self.index_for_view(view).update(view.window().folders())

        # Display phantoms for embeds
        self.phantom_set = sublime.PhantomSet(view)
        phantoms = []
        for region in view.find_by_selector('meta.brackets markup.raw.block'):
            link = view.substr(region)
            note_name = note_name_from_link(link)
            note_path = path_to_note(view, note_name)
            
            if file_extension(note_name) == None:
                note_content = open(note_path, 'r').read()
                phantom = sublime.Phantom(region, note_content, sublime.LAYOUT_BLOCK)
                phantoms.append(phantom)

        self.phantom_set.update(phantoms)

    # File load handler
    def on_load(self, view):
        note = os.path.basename(view.file_name())[:-3]

        links = self.index_for_view(view).links(note)
        if links:
            log("---- Links ----")
            for link in links:
                log(link)

        backlinks = self.index_for_view(view).backlinks(note)
        if backlinks:
            log("---- Backlinks ----")
            for backlink in backlinks:
                log(backlink)

    # Completion handler
    def on_query_completions(self, view, prefix, locations):

        # [[Link]] completion
        if view.match_selector(locations[0], 'meta.brackets'):
            index = self.index_for_view(view)
            return [(note + '\tNote', note) for note in index.notes.keys() if note.startswith(prefix)]

        return None