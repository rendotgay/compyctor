from tkinter import ttk
DARK_PRIMARY = "#ff008b"
DARK_BG = "#222222"
DARK_FG = "#ffffff"
DARK_FIELD_BG = "#111111"
DARK_HOVER = "#4d4d4d"

LIGHT_PRIMARY = "#ff9bad"
LIGHT_BG = "#f5fcfe"
LIGHT_FG = "#000000"
LIGHT_FIELD_BG = "#ebf9fe"

LIGHT_HOVER = "#cef0fd"
LIGHT_INFO = "#33FF5C"
LIGHT_WARNING = "#FF7738"
LIGHT_ERROR = "#FF4747"


class MainStyle(ttk.Style):
    def __init__(self):
        super().__init__()
        self.theme_use("clam")
        self.add_theme("light", LIGHT_BG, LIGHT_FG, LIGHT_FIELD_BG, LIGHT_PRIMARY, LIGHT_HOVER)
        self.add_theme("dark", DARK_BG, DARK_FG, DARK_FIELD_BG, DARK_PRIMARY, DARK_HOVER)


    def add_theme(self, name, bg, fg, field_bg, primary, hover, parent="clam", arrowsize=0):
        self.theme_create(name, parent=parent, settings={
            ".": {
                "configure": {
                    "background": bg,
                    "foreground": fg,
                    "insertcolor": primary,
                    "fieldbackground": field_bg,
                    "selectbackground": primary,
                    "arrowsize": 0,
                },
                "map": {
                    "background": [
                        ("pressed", primary),
                        ("active", hover)
                    ],
                    "foreground": [
                        ("pressed", fg),
                        ("active", fg)
                    ]
                }
            },
            "TButton": {
                "configure": {
                    "background": field_bg,
                    "foreground": fg,
                },
            },
            "Treeview": {
                "configure": {
                    "background": field_bg,
                    "foreground": fg,
                    "bordercolor": fg,
                    "borderwidth": "1px"
                },
                "map": {
                    "background": [("selected", primary)],
                    "foreground": [("selected", fg)]
                }
            },
            "TScrollbar": {
                "configure": {
                    "background": "#454545",
                    "troughcolor": bg,
                    "bordercolor": hover,
                    "lightcolor": "#2d2d2d",
                    "darkcolor": "#2d2d2d",
                    "arrowcolor": "#eeeeee",
                    "arrowsize": 12
                },
                "map": {
                    "background": [("active", hover)],
                    "arrowcolor": [("active", field_bg)]
                }
            },
            "ScrolledText": {
                "configure": {
                    "bg": field_bg,
                }
            }
        })
        self.theme_use(name)

        elem = f"{name}.pbar"
        self.element_create(elem, "from", "clam")
        self.layout("TProgressbar", [
            ("Horizontal.Progressbar.trough", {
                "sticky": "nswe",
                "children": [(elem, {"side": "left", "sticky": "ns"})]
            })
        ])
        self.configure("TProgressbar",
           troughcolor=field_bg,
           background=primary,
           lightcolor=primary,
           darkcolor=primary,
           bordercolor=field_bg,
           borderwidth=0,
           thickness=20,
        )

        self.configure(elem,
           background=primary,
           lightcolor=primary,
           darkcolor=primary,
        )