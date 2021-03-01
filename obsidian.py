import os
import re
import sublime
import sublime_plugin

def collect_links(file):
    pattern = re.compile('\\[\\[.*?\\]\\]')

    links = []
    for line in file.readlines():
        matches = pattern.findall(line)
        for match in matches:
            links.append(match[2:-2])
    return links


class ObsidianOpenNoteCommand(sublime_plugin.TextCommand):

    def is_enabled(self, event=None):
        layout_pos = self.view.window_to_layout((event['x'], event['y']))
        text_pos = self.view.layout_to_text(layout_pos)
        return self.view.match_selector(text_pos, 'meta.brackets markup.underline.link')

    def want_event(self):
        return True

    def run(self, edit, event=None):
        layout_pos = self.view.window_to_layout((event['x'], event['y']))
        text_pos = self.view.layout_to_text(layout_pos)
        region = self.view.extract_scope(text_pos)
        note = self.view.substr(region)
        #self.view.window().open_file(self.view.window().folders()[0] + '/' + note + '.md')

class Note:

    def __init__(self, path, links):
        self.path = path
        self.links = links
        pass

class Index:

    def __init__(self):
        # set of open folders
        self.folders = set()
        # map from names to Notes
        self.notes = {}

    def update(self, new_folders):
        new_set = set(new_folders)

        # if the set of folders has changed, just re-index everything
        if len(new_set ^ self.folders) > 0:
            print("update index")
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
    def links(self, note):
        if note in self.notes:
            return self.notes[note].links
        return []

    # return the backlinks for a note
    def backlinks(self, note):
        if note in self.notes:
            return self.notes[note].links
        return []

class ObsidianListener(sublime_plugin.EventListener):

    def __init__(self):
        # Map from windows to indexes
        self.indexes = {}

    def on_activated(self, view):
        # Update the index associated with the view's window
        key = view.window().id()
        if key in self.indexes:
            index = self.indexes[key]
        else:
            index = Index()
            self.indexes[key] = index
            
        index.update(view.window().folders())

    def on_load(self, view):
        note = os.path.basename(view.file_name())[:-3]

        links = self.indexes[view.window().id()].links(note)
        if links:
            print("---- Links ----")
            for link in links:
                print(link)

        backlinks = self.indexes[view.window().id()].backlinks(note)
        if backlinks:
            print("---- Backlinks ----")
            for backlink in backlinks:
                print(backlink)

    def on_query_completions(self, view, prefix, locations):
        
        if view.match_selector(locations[0], 'meta.brackets'):
            index = self.indexes[view.window().id()]
            return [(note + '\tNote', note) for note in index.notes.keys() if note.startswith(prefix)]

        return None