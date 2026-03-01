from kivy.lang import Builder

from kivymd.app import MDApp


KV = '''
MDScreen:
    md_bg_color: self.theme_cls.backgroundColor

    MDSmartTile:
        pos_hint: {"center_x": .5, "center_y": .5}
        size_hint: None, None
        size: "589dp", "400dp"
        overlap: True

        MDSmartTileImage:
            source: "../images/ZMAR-048.jpg"
            radius: [dp(24), dp(24), dp(24), dp(24)]

        MDSmartTileOverlayContainer:
            md_bg_color: .7, .7, .9, .9
            adaptive_height: True
            padding: "8dp"
            spacing: "8dp"
            radius: [0, 0, dp(24), dp(24)]

            MDIconButton:
                icon: "heart-outline"
                theme_icon_color: "Custom"
                icon_color: 1, 0, 0, 1
                pos_hint: {"center_y": .5}

            MDLabel:
                text: "Ibanez GRG121DX-BKF"
                theme_text_color: "Custom"
                text_color: "black"

            MDIconButton:
                icon: "play-outline"
                theme_icon_color: "Custom"
                icon_color: 1, 0, 0, 1
                pos_hint: {"center_y": .5}

            MDIconButton:
                icon: "dots-vertical"
                theme_icon_color: "Custom"
                icon_color: 1, 0, 0, 1
                pos_hint: {"center_y": .5}

            MDIconButton:
                icon: "menu"
                theme_icon_color: "Custom"
                icon_color: 1, 0, 0, 1
                pos_hint: {"center_y": .5}
            MDIconButton:
                icon: "plus"
                theme_icon_color: "Custom"
                icon_color: 1, 0, 0, 1
                pos_hint: {"center_y": .5}
'''

class Example(MDApp):
    def build(self):
        self.theme_cls.theme_style = "Dark"
        return Builder.load_string(KV)


Example().run()