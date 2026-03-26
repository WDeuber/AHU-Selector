import tkinter as tk
from PIL import Image, ImageTk
import json
import math


class AHUComponent:
    def __init__(self, component_source,component_name,nominal_size):
        self.name = component_name      # component_name: eg "Heat_Coil"
        self.size = nominal_size        # nominal_size: eg "60"

        try:
            self.data = component_source[component_name][nominal_size]
        except KeyError:
            raise ValueError(f"Invalid component or size: {component_name} / {nominal_size}")
        try:
            self.label_name = component_source[component_name]["label"]
        except KeyError:
            raise ValueError(f"Cannot find label")


    @property
    def dimensions(self):
        return self.data["dimensions"]
    @property
    def length(self):
        return self.data["dimensions"]["length"]
    @property
    def width(self):
        return self.data["dimensions"]["width"]
    @property
    def height(self):
        return self.data["dimensions"]["height"]
    @property
    def weight(self):
        return self.data["weight"]
    @property
    def image_path(self):
        return self.data["image"]
    @property
    def isp(self):
        return self.data["isp"]
    @property
    def label(self):
        return self.label_name



class AHU:
    increments = [45, 60, 85, 105, 125, 155, 180, 200, 240, 300, 350, 400, 450, 500]

    def __init__(self,component_source, cfm=0, esp=0):
        self.component_source = component_source        # component_source as ahu_components json file
        self.components = []            # supply components
        self.return_components = []     # return components (dual tunnel only)
        self.tunnel_mode = "single"     # "single" or "dual"
        self.cfm = cfm
        self.esp = esp

    def add_component(self, name, size, side="supply"):
        comp = AHUComponent(self.component_source, name, size)
        if side == "return" and self.tunnel_mode == "dual":
            self.return_components.append(comp)
        else:
            self.components.append(comp)

    def remove_component(self, index, side="supply"):
        lst = self.return_components if side == "return" else self.components
        if 0 <= index < len(lst):
            lst.pop(index)

    def move_component(self, from_index, to_index, side="supply"):
        lst = self.return_components if side == "return" else self.components
        if from_index == to_index:
            return
        if from_index < 0 or from_index >= len(lst):
            return
        if to_index < 0 or to_index > len(lst):
            return
        if from_index < to_index:
            to_index -= 1

        component = lst.pop(from_index)
        lst.insert(to_index, component)

    def move_component_between_rows(self, from_index, from_side, to_index, to_side):
        src = self.return_components if from_side == "return" else self.components
        dst = self.return_components if to_side == "return" else self.components
        if from_index < 0 or from_index >= len(src):
            return
        component = src.pop(from_index)
        to_index = min(to_index, len(dst))
        dst.insert(to_index, component)

    def size_from_cfm(self):
        if self.cfm == 0:
            return None

        req_size = math.ceil(self.cfm/100)
        for s in self.increments:
            if s >= req_size:
                return str(s)
        return None

    @property
    def model_size(self):
        return self.size_from_cfm()
    @property
    def length(self):
        return sum(c.length for c in self.components)
    @property
    def weight(self):
        supply_weight = sum(c.weight for c in self.components)
        return_weight = sum(c.weight for c in self.return_components)
        return supply_weight + return_weight
    @property
    def dimensions(self):
        all_comps = self.components + self.return_components
        return {
            "length": self.length,
            "width": max((c.dimensions["width"] for c in all_comps), default=0),
            "height": max((c.dimensions["height"] for c in all_comps), default=0)
        }
    @property
    def count(self):
        return len(self.components) + len(self.return_components)
    @property
    def isp(self):
        return sum(c.isp for c in self.components)
    @property
    def tsp(self):
        return self.esp + self.isp
    @property
    def bhp(self):
        return (self.tsp*self.cfm)/(6356*0.65)

class DropdownSection(tk.Frame):
    def __init__(self, parent, title, max_columns=4):
        super().__init__(parent, bg="#F5F5F5", bd=1, relief="solid")

        self.expanded = False
        self.max_columns = max_columns
        self.current_row = 0
        self.current_col = 0

        self.header = tk.Button(
            self,
            text=f"{title} ▼",
            anchor="w",
            relief="flat",
            bg="#D0D0D0",
            command=self.toggle
        )
        self.header.pack(fill="x")
        self.content = tk.Frame(self, bg="#F5F5F5")

    def toggle(self):
        if self.expanded:
            self.content.pack_forget()
            self.header.config(text=self.header.cget("text").replace("▲", "▼"))
        else:
            self.content.pack(fill="x", padx=6, pady=4)
            self.header.config(text=self.header.cget("text").replace("▼", "▲"))

        self.expanded = not self.expanded

    def add_button(self, image, label, command):
        btn=tk.Button(self.content, image=image, text=label, compound="top", width=100, height=120, command=command)
        btn.image = image
        btn.grid(row=self.current_row, column=self.current_col, padx=4, pady=4, sticky="n")
        self.current_col += 1
        if self.current_col >= self.max_columns:
            self.current_col = 0
            self.current_row += 1

class ComponentRow(tk.Frame):
    def __init__(self, parent, component, on_delete, on_drag):
        super().__init__(parent, bg="#FFFFFF", height=36)

        self.component = component
        self.on_delete = on_delete
        self.on_drag = on_drag

        self.pack(fill="x", pady=2)
        self.pack_propagate(False)

        self.build_list_ui()
        self.bind_events()

    def build_list_ui(self):
        self.label = tk.Label(self, text=self.component.label_name, anchor="w", bg="#FFFFFF", padx=8)
        self.label.pack(side="left", fill="x", expand=True)

        self.delete_btn = tk.Label(self, text="🗑", cursor="hand2", bg="#FFFFFF")
        self.delete_btn.place(relx=1, rely=0.5, anchor="e")      #pack(side="right", padx=6)
        self.delete_btn.place_forget()   #hidden by default
        self.delete_btn.bind("<Button-1>", self.on_delete_click)

    def bind_events(self):
        for widget in (self, self.label):
            widget.bind("<Enter>", self.on_hover)
            widget.bind("<Leave>", self.on_leave)
            widget.bind("<Button-1>", self.start_drag)
            widget.bind("<B1-Motion>", self.drag)
            widget.bind("<ButtonRelease-1>",self.stop_drag)

    def set_active(self, active=True):
        color = "#CCE0FF" if active else "#FFFFFF"
        self.config(bg=color)
        self.label.config(bg=color)
        self.delete_btn.config(bg=color)

    def on_hover(self, event):
        if getattr(self, "dragging", False):
            return
        self.set_active(True)
        self.delete_btn.place(relx=1, rely=0.5, anchor="e")

    def on_leave(self, event):
        if getattr(self, "dragging", False):
            return
        if event.widget is not self:
            return

        self.set_active(False)
        self.delete_btn.place_forget()

    def start_drag(self, event):
        self.dragging = True
        self.set_active(True)
        self.on_drag("start", self)

    def drag(self, event):
        self.on_drag("drag", self, event.y_root)

    def stop_drag(self, event):
        self.dragging = False
        self.on_drag("end", self)

    def on_delete_click(self, event):
        event.widget.master.on_delete(self)
        print("Button Clicked")

class ComponentList(tk.Frame):
    def __init__(self, parent, ahu, on_change, side="supply"):
        super().__init__(parent)
        self.ahu = ahu
        self.on_change = on_change
        self.side = side
        self.rows = []

        self.drag_row = None
        self.drag_index = None
        self.drag_target = None

        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.scroll = tk.Scrollbar(self, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scroll.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scroll.pack(side="right", fill="y")

        self.list_frame = tk.Frame(self.canvas)
        self.canvas.create_window((0,0), window=self.list_frame, anchor="nw", width=self.canvas.winfo_width())
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig("all", width=e.width))

        self.list_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        self.list_drag_indicator = tk.Frame(self.list_frame, height=2, bg="#4a90e2")  # List drop indicator
        self.list_drag_indicator.place_forget()

    def refresh(self):
        print("Components Refreshed!")
        for row in self.rows:
            row.destroy()
        self.rows.clear()

        components = self.ahu.return_components if self.side == "return" else self.ahu.components
        for comp in components:
            row = ComponentRow(self.list_frame, comp, self.on_delete, self.handle_drag)
            self.rows.append(row)

    def on_delete(self, row):
        print("Delete Button Pressed")
        index = self.rows.index(row)
        self.ahu.remove_component(index, side=self.side)
        self.on_change()

    def show_drag_indicator(self, y):
        self.list_drag_indicator.place(x=0, y=y, relwidth=1)
        self.list_drag_indicator.lift()

    def handle_drag(self, action, row, y=None):
        if action == "start":
            self.drag_row = row
            self.drag_index = self.rows.index(row)
            self.drag_target = self.drag_index
        elif action == "drag":
            if self.drag_row is None or self.drag_index is None:
                return

            mouse_y = self.list_frame.winfo_pointery() - self.list_frame.winfo_rooty()

            for i, row in enumerate(self.rows):
                if row is self.drag_row:
                    continue
                row_top = row.winfo_y()
                row_mid = row.winfo_y() + row.winfo_height() // 2

                if mouse_y < row_mid:
                    self.drag_target = i
                    self.show_drag_indicator(row_top)
                    break

            else:       # If below all rows
                self.drag_target = len(self.rows)
                last = self.rows[-1]
                self.show_drag_indicator(last.winfo_y() + last.winfo_height())

        elif action == "end":
            self.list_drag_indicator.place_forget()
            if self.drag_index is not None and self.drag_target is not None:
                self.ahu.move_component(self.drag_index, self.drag_target, side=self.side)

            self.drag_row = None
            self.drag_index = None
            self.drag_target = None

            self.on_change()

class AHUGUI:
    def __init__(self, root, ahu):
        self.root = root
        self.ahu = ahu
        self.root.title("AHU Builder")

        # Split window into left + right
        self.left_frame = tk.Frame(self.root, width=500, bg="white")
        self.left_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        self.left_frame.pack_propagate(False)

        self.right_frame = tk.Frame(root, bg="#F0F0F0")
        self.right_frame.pack(side="right", fill="both", expand=True, padx=5, pady=5)

        # Left side
        self.build_left_panel()                 # Left side (CFM)
        self.build_component_dropdowns()        # Component List Dropdowns
        self.build_right_panel()                # Right side (ESP)

        # Component canvas + dropdown updates
        def _on_component_frame_configure(event):
            self.component_canvas.configure(scrollregion=self.component_canvas.bbox("all"))
        def _on_canvas_configure(event):
            self.component_canvas.itemconfig(self.component_window, width=event.width)
        def _on_mousewheel(event):
            self.component_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.component_frame.bind("<Configure>", _on_component_frame_configure)
        self.component_canvas.bind("<Configure>", _on_canvas_configure)
        self.component_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Image drag states
        self.dragged_image = None
        self.drag_start_index = None
        self.drag_start_side = "supply"
        self.drag_target_index = None
        self.drag_target_side = "supply"
        self.visual_drag_indicator = None

        # References to display frames for dual tunnel
        self.supply_display = None
        self.return_display = None

    def update_cfm(self):
        try:
            self.ahu.cfm = int(self.airflow_entry.get())
        except ValueError:
            self.ahu.cfm = 0

        self.update_display()

    def update_esp(self):
        try:
            self.ahu.esp = int(self.esp_entry.get())
        except:
            self.ahu.esp = 0

        self.update_display()

    def build_left_panel(self):

        input_row = tk.Frame(self.left_frame,bg="#F5F5F5")
        input_row.pack(fill="x", padx=10, pady=10)

        left_half = tk.Frame(input_row, bg="#F5F5F5")           # CFM Frame
        left_half.pack(side="left", fill="x", expand=True)
        right_half = tk.Frame(input_row, bg="#F5F5F5")          # ESP Frame
        right_half.pack(side="right", fill="x", expand=True)

        self.build_cfm_input(left_half)
        self.build_esp_input(right_half)

        # Tunnel mode selector
        tunnel_row = tk.Frame(self.left_frame, bg="#F5F5F5")
        tunnel_row.pack(fill="x", padx=10, pady=(0, 8))

        tk.Label(tunnel_row, text="Tunnel Type:", font=("Arial", 10), bg="#F5F5F5").pack(side="left", padx=(0, 8))

        self.tunnel_var = tk.StringVar(value="Single Tunnel")
        tunnel_options = ["Single Tunnel", "Dual Tunnel"]
        tunnel_menu = tk.OptionMenu(tunnel_row, self.tunnel_var, *tunnel_options, command=self.on_tunnel_change)
        tunnel_menu.config(width=14)
        tunnel_menu.pack(side="left")

    def on_tunnel_change(self, value):
        new_mode = "dual" if value == "Dual Tunnel" else "single"
        if new_mode == self.ahu.tunnel_mode:
            return
        self.ahu.tunnel_mode = new_mode
        if new_mode == "single":
            self.ahu.return_components = []
        # Rebuild list area to reflect new layout
        self.build_list_area()
        self.update_visual_area()
        self.update_summary_area()

    def build_cfm_input(self, parent):
        frame = tk.Frame(parent, bg="#F5F5F5")
        frame.pack(expand=True, pady=(0,10))

        tk.Label(frame, text="Airflow CFM:",font=("Arial", 10), bg="#F5F5F5").pack(anchor="center")

        self.airflow_entry = tk.Entry(frame, justify="center", width=20)
        self.airflow_entry.pack(pady=(2,0))

        self.airflow_entry.bind("<KeyRelease>", lambda e: self.update_cfm())        # Live update

    def build_esp_input(self, parent):
        frame = tk.Frame(parent, bg="#F5F5F5")
        frame.pack(expand=True, pady=(0,10))

        tk.Label(frame, text="External Static Pressure (in. w.g.)", font=("Arial", 10), bg="#F5F5F5").pack(anchor="center")

        self.esp_entry = tk.Entry(frame, justify="center", width=20)
        self.esp_entry.pack(pady=(2,0))

        self.esp_entry.bind("<KeyRelease>", lambda e: self.update_esp())

    def build_component_dropdowns(self):
        # Add canvas + scrollbar
        self.component_canvas = tk.Canvas(
            self.left_frame,
            highlightthickness=0
        )

        self.component_scrollbar = tk.Scrollbar(
            self.left_frame,
            orient="vertical",
            command=self.component_canvas.yview
        )

        self.component_canvas.configure(yscrollcommand=self.component_scrollbar.set)
        self.component_canvas.pack(side="left", fill="both", expand=True)
        self.component_scrollbar.pack(side="right", fill="y")

        # Scrollable inner frame
        self.component_frame = tk.Frame(self.component_canvas)

        self.component_window = self.component_canvas.create_window(
            (0, 0),
            window=self.component_frame,
            anchor="nw"
        )



        categories = {
            "Fans": [
                ("Centrifugal Fan (90TH-270BH)", "Centrifugal Fan_90TH_270BH", "images/Centrifugal_Fan_90TH_270BH.png"),
                ("Centrifugal Fan (360UB-180DB)", "Centrifugal Fan_360UB_180DB",
                 "images/Centrifugal_Fan_360UB_180DB.png"),
                ("Plenum Fan", "Plenum_Fan", "images/Plenum_Fan.png")
            ],
            "Coils": [
                ("Heat Coil", "Heat_Coil", "images/Heat_Coil.png"),
                ("Integrated FBP HC", "Integ_FBP_HC", "images/Integ_FPB_HC.png"),
                ("Conv FBP HC", "Conv_FBP_HC", "images/Conv_FBP_HC.png"),
                ("Cooling Coil", "Cool_Coil", "images/Cool_Coil.png"),
                ("Conv FBP CC", "Conv_FBP_CC", "images/Conv_FBP_CC.png"),
                ("Steam Humidifier", "Steam_Humidifier", "images/Steam_Humidifier.png"),
                ("Sprayed Coil", "Sprayed_Coil", "images/Sprayed_Coil.png")
            ],
            "Filters": [
                ("Eliminator", "Elim", "images/Elim.png"),
                ("Flat Filter", "Flat_Filter", "images/Flat_Filter.png"),
                ("Angle Filter", "Angle_Filter", "images/Angle_Filter.png"),
                ("Hi-Eff Filter (12 rigid)", "Hi_Eff_Filter_12rigid", "images/Hi_Eff_Filter.png"),
                ("Hi-Eff Filter (22 bag)", "Hi_Eff_Filter_22bag", "images/Hi_Eff_Filter.png"),
                ("Hi-Eff Filter (28 bag)", "Hi_Eff_Filter_28bag", "images/Hi_Eff_Filter.png"),
                ("Hi-Eff Filter (32 bag)", "Hi_Eff_Filter_32bag", "images/Hi_Eff_Filter.png"),
                ("Roll Filter", "Roll_Filter", "images/Roll_Filter.png")

            ],
            "Damper / Sound Trap": [
                ("Face Damper", "Face_Damper", "images/Face_Damper.png"),
                ("Louver w/ Screen", "Louver_w_Screen", "images/Louver_w_Screen.png"),
                ("Sound Trap", "Sound_Trap", "images/Sound_Trap.png")

            ],
            "Plenum": [
                ("Plenum", "Plenum", "images/Plenum.png"),
                ("Plenum w/Door", "Plenum_w_Door", "images/Plenum_w_Door.png"),
                ("Blender", "Blender", "images/Blender.png"),
                ("Mixing Box Door", "Mixing_Box_Door", "images/Mixing_Box_Door.png"),
                ("Discharge Plenum", "Discharge_Plenum", "images/Discharge_Plenum.png"),
                ("Diffuser Plenum", "Diffuser_Plenum", "images/Diffuser_Plenum.png")
            ],
            "Economizer": [
                ("Economizer Indoor", "Economizer_Indoor", "images/Economizer_Indoor.png"),
                ("Economizer Outdoor", "Economizer_Outdoor", "images/Economizer_Outdoor.png")
            ]
        }
        for category_name, items in categories.items():
            dropdown = DropdownSection(self.component_frame, category_name)
            dropdown.pack(fill="x", pady=(0,8))

            for display_name, component_key, image_path in items:
                img = self.load_icon(image_path)

                dropdown.add_button(image=img, label=display_name, command=lambda k=component_key: self.handle_add_component(k))



    def load_icon(self, path, size=(70,70)):
        if not hasattr(self, "_icon_cache"):
            self._icon_cache = {}
        if path not in self._icon_cache:
            try:
                img = Image.open(path).resize(size)
            except Exception:
                img = Image.open("images/placeholder.png").resize(size)

            self._icon_cache[path] = ImageTk.PhotoImage(img)

        return self._icon_cache[path]

    def build_right_panel(self):
        self.right_frame = tk.Frame(self.root, bg="#F0F0F0")
        self.right_frame.pack(side="right", fill="both", expand=True)

        #split to top/bottom
        self.visual_frame = tk.Frame(self.right_frame, bg="white", height=300)
        self.visual_frame.pack(fill="both", expand=True)

        self.bottom_frame = tk.Frame(self.right_frame, bg="#E8E8E8", height=200)
        self.bottom_frame.pack(fill="both", expand=True)

        self.build_visual_area()        # Component Diagram
        self.build_bottom_area()        # Component List & Summary

    def build_visual_area(self):
        title=tk.Label(
            self.visual_frame,
            text="AHU Layout",
            font=("Arial", 14, "bold"),
            bg="white"
        )
        title.pack(anchor="w", padx=10, pady=5)

        self.image_container = tk.Frame(self.visual_frame, bg="white")
        self.image_container.pack(fill="both", expand=True, padx=10, pady=10)

    def update_visual_area(self):
        for widget in self.image_container.winfo_children():
            widget.destroy()
        self.supply_display = None
        self.return_display = None

        if self.ahu.tunnel_mode == "dual":
            self._build_dual_tunnel_visual()
        else:
            self._build_single_tunnel_visual()

    def _build_single_tunnel_visual(self):
        for index, comp in enumerate(self.ahu.components):
            img = self.get_component_image(comp)

            btn = tk.Label(
                self.image_container,
                image=img,
                text=f"{comp.label}\nSize {comp.size}",
                compound="top",
                bg="white",
                relief="solid",
                borderwidth=1,
                padx=5,
                pady=5
            )
            btn.image = img
            btn.pack(side="left", padx=5)

            btn.drag_index = index
            btn.drag_side = "supply"
            btn.bind("<Button-1>", self._start_image_drag)
            btn.bind("<B1-Motion>", self._on_image_drag)
            btn.bind("<ButtonRelease-1>", self._end_image_drag)

    def _build_dual_tunnel_visual(self):
        # Return row (top)
        return_wrapper = tk.Frame(self.image_container, bg="#F0F0F0", bd=1, relief="groove")
        return_wrapper.pack(fill="x", pady=(0, 4))

        tk.Label(
            return_wrapper,
            text="Return",
            font=("Arial", 10, "bold"),
            bg="#F0F0F0",
            width=7,
            anchor="center"
        ).pack(side="left", padx=6, pady=4)

        self.return_display = tk.Frame(return_wrapper, bg="white")
        self.return_display.pack(side="left", fill="both", expand=True, padx=4, pady=4)

        for index, comp in enumerate(self.ahu.return_components):
            img = self.get_component_image(comp)
            btn = tk.Label(
                self.return_display,
                image=img,
                text=f"{comp.label}\nSize {comp.size}",
                compound="top",
                bg="white",
                relief="solid",
                borderwidth=1,
                padx=5,
                pady=5
            )
            btn.image = img
            btn.pack(side="left", padx=5)
            btn.drag_index = index
            btn.drag_side = "return"
            btn.bind("<Button-1>", self._start_image_drag)
            btn.bind("<B1-Motion>", self._on_image_drag)
            btn.bind("<ButtonRelease-1>", self._end_image_drag)

        # Supply row (bottom)
        supply_wrapper = tk.Frame(self.image_container, bg="#F0F0F0", bd=1, relief="groove")
        supply_wrapper.pack(fill="x", pady=(4, 0))

        tk.Label(
            supply_wrapper,
            text="Supply",
            font=("Arial", 10, "bold"),
            bg="#F0F0F0",
            width=7,
            anchor="center"
        ).pack(side="left", padx=6, pady=4)

        self.supply_display = tk.Frame(supply_wrapper, bg="white")
        self.supply_display.pack(side="left", fill="both", expand=True, padx=4, pady=4)

        for index, comp in enumerate(self.ahu.components):
            img = self.get_component_image(comp)
            btn = tk.Label(
                self.supply_display,
                image=img,
                text=f"{comp.label}\nSize {comp.size}",
                compound="top",
                bg="white",
                relief="solid",
                borderwidth=1,
                padx=5,
                pady=5
            )
            btn.image = img
            btn.pack(side="left", padx=5)
            btn.drag_index = index
            btn.drag_side = "supply"
            btn.bind("<Button-1>", self._start_image_drag)
            btn.bind("<B1-Motion>", self._on_image_drag)
            btn.bind("<ButtonRelease-1>", self._end_image_drag)

    def get_component_image(self, component_name):
        try:
            img = Image.open(component_name.image_path).resize((90, 90))
            return ImageTk.PhotoImage(img)
        except:
            return None

    def _get_visual_slots_for(self, frame):
        widgets = frame.winfo_children()
        if not widgets:
            return [0]
        slots = [widgets[0].winfo_x()]
        for w in widgets:
            slots.append(w.winfo_x() + w.winfo_width())
        return slots

    def _get_visual_slots(self):
        return self._get_visual_slots_for(self.image_container)

    def _start_image_drag(self, event):
        lbl = event.widget
        self.dragged_image = lbl
        self.drag_start_index = lbl.drag_index
        self.drag_start_side = lbl.drag_side
        self.drag_target_side = lbl.drag_side

        self.visual_drag_indicator = tk.Frame(
            self.visual_frame,
            width=4,
            height=lbl.winfo_height() - 6,
            bg="#4a90e2"
        )

    def _on_image_drag(self, event):
        if self.ahu.tunnel_mode == "dual" and self.return_display and self.supply_display:
            # Determine which row the mouse is over
            mouse_y_root = event.y_root
            return_top = self.return_display.winfo_rooty()
            return_bottom = return_top + self.return_display.winfo_height()
            supply_top = self.supply_display.winfo_rooty()
            supply_bottom = supply_top + self.supply_display.winfo_height()

            # Pick the closer row based on mouse position
            dist_return = min(abs(mouse_y_root - return_top), abs(mouse_y_root - return_bottom))
            dist_supply = min(abs(mouse_y_root - supply_top), abs(mouse_y_root - supply_bottom))

            if return_top <= mouse_y_root <= return_bottom:
                target_display = self.return_display
                self.drag_target_side = "return"
            elif supply_top <= mouse_y_root <= supply_bottom:
                target_display = self.supply_display
                self.drag_target_side = "supply"
            elif dist_return <= dist_supply:
                target_display = self.return_display
                self.drag_target_side = "return"
            else:
                target_display = self.supply_display
                self.drag_target_side = "supply"

            mouse_x = event.x_root - target_display.winfo_rootx()
            slots = self._get_visual_slots_for(target_display)

            nearest_index = min(range(len(slots)), key=lambda i: abs(slots[i] - mouse_x))
            self.drag_target_index = nearest_index

            # Place indicator relative to visual_frame
            abs_x = target_display.winfo_rootx() - self.visual_frame.winfo_rootx()
            abs_y = target_display.winfo_rooty() - self.visual_frame.winfo_rooty()
            slot_x = abs_x + slots[nearest_index]
            offset = 3 if nearest_index == 0 else 13
            self.visual_drag_indicator.place(x=slot_x + offset, y=abs_y + 3)
        else:
            mouse_x = event.x_root - self.visual_frame.winfo_rootx()
            slots = self._get_visual_slots()
            nearest_index = min(range(len(slots)), key=lambda i: abs(slots[i] - mouse_x))
            self.drag_target_index = nearest_index
            self.drag_target_side = "supply"

            if nearest_index == 0:
                self.visual_drag_indicator.place(x=slots[nearest_index] + 3, y=102)
            else:
                self.visual_drag_indicator.place(x=slots[nearest_index] + 13, y=102)

    def _end_image_drag(self, event):
        if (
            self.drag_start_index is not None
            and self.drag_target_index is not None
        ):
            if self.drag_start_side == self.drag_target_side:
                if self.drag_start_index != self.drag_target_index:
                    self.ahu.move_component(
                        self.drag_start_index,
                        self.drag_target_index,
                        side=self.drag_start_side
                    )
            else:
                self.ahu.move_component_between_rows(
                    self.drag_start_index,
                    self.drag_start_side,
                    self.drag_target_index,
                    self.drag_target_side
                )

            self.update_display()

        if self.visual_drag_indicator:
            self.visual_drag_indicator.destroy()

        self.dragged_image = None
        self.drag_start_index = None
        self.drag_start_side = "supply"
        self.drag_target_index = None
        self.drag_target_side = "supply"


    def build_bottom_area(self):
        self.list_frame = tk.Frame(self.bottom_frame, bg="#E8E8E8")
        self.list_frame.pack(side="left", fill="both", expand=True)

        self.summary_frame = tk.Frame(self.bottom_frame, bg="#DADADA")
        self.summary_frame.pack(side="right", fill="both", expand=True)

        self.build_list_area()          # Component List
        self.build_summary_area()       # Summary

    def build_list_area(self):
        # Clear existing list area content
        for widget in self.list_frame.winfo_children():
            widget.destroy()
        self.component_list = None
        self.supply_component_list = None
        self.return_component_list = None

        title = tk.Label(
            self.list_frame,
            text="Components Included",
            font=("Arial", 14, "bold"),
            bg="#E8E8E8"
        )
        title.pack(anchor="center", padx=8, pady=4)

        if self.ahu.tunnel_mode == "dual":
            dual_frame = tk.Frame(self.list_frame, bg="#E8E8E8")
            dual_frame.pack(fill="both", expand=True)

            # Return side (left column)
            return_col = tk.Frame(dual_frame, bg="#E8E8E8", bd=1, relief="groove")
            return_col.pack(side="left", fill="both", expand=True, padx=(0, 2), pady=2)

            tk.Label(
                return_col,
                text="Return",
                font=("Arial", 11, "bold"),
                bg="#E8E8E8"
            ).pack(anchor="center", pady=(4, 2))

            self.return_component_list = ComponentList(
                parent=return_col,
                ahu=self.ahu,
                on_change=self.update_display,
                side="return"
            )
            self.return_component_list.pack(fill="both", expand=True)
            self.return_component_list.refresh()

            # Supply side (right column)
            supply_col = tk.Frame(dual_frame, bg="#E8E8E8", bd=1, relief="groove")
            supply_col.pack(side="right", fill="both", expand=True, padx=(2, 0), pady=2)

            tk.Label(
                supply_col,
                text="Supply",
                font=("Arial", 11, "bold"),
                bg="#E8E8E8"
            ).pack(anchor="center", pady=(4, 2))

            self.supply_component_list = ComponentList(
                parent=supply_col,
                ahu=self.ahu,
                on_change=self.update_display,
                side="supply"
            )
            self.supply_component_list.pack(fill="both", expand=True)
            self.supply_component_list.refresh()
        else:
            self.component_list = ComponentList(
                parent=self.list_frame,
                ahu=self.ahu,
                on_change=self.update_display,
                side="supply"
            )
            self.component_list.pack(fill="both", expand=True)
            self.component_list.refresh()

    def build_summary_area(self):
        title = tk.Label(
            self.summary_frame,
            text="AHU Summary",
            font=("Arial", 14, "bold"),
            bg="#DADADA"
        )
        title.pack(anchor="center", padx=8, pady=4)

        self.summary_labels = {}

        fields = [
            "Model Size",
            "CFM",
            "TSP",
            "Overall Dimensions",
            "Total Weight",
            "BHP"
        ]

        for field in fields:
            lbl = tk.Label(
                self.summary_frame,
                text=f"{field}: -",
                font=("Arial", 10),
                bg="#DADADA",
                anchor="w"
            )
            lbl.pack(fill="x", padx=8, pady=2)
            self.summary_labels[field] = lbl

    def update_summary_area(self):
        self.summary_labels["Model Size"].config(
            text=f"Model Size: {self.ahu.model_size}"
        )
        self.summary_labels["CFM"].config(
            text=f"CFM: {self.ahu.cfm:,}"
        )
        self.summary_labels["TSP"].config(
            text=f"TSP: {self.ahu.tsp:.2f} in.w.g."
        )
        dims = self.ahu.dimensions
        self.summary_labels["Overall Dimensions"].config(
            text=f"Overall Dimensions: {dims['length']} L x {dims['width']} W x {dims['height']} H"
        )
        self.summary_labels["Total Weight"].config(
            text=f"Total Weight: {self.ahu.weight} lb"
        )
        self.summary_labels["BHP"].config(
            text=f"BHP: {round(self.ahu.bhp,3)}"
        )

    def refresh_component_lists(self):
        if self.ahu.tunnel_mode == "dual":
            if self.return_component_list:
                self.return_component_list.refresh()
            if self.supply_component_list:
                self.supply_component_list.refresh()
        else:
            if self.component_list:
                self.component_list.refresh()

    def update_display(self):
        self.refresh_component_lists()      # Update component list
        self.update_visual_area()           # Update component diagram
        self.update_summary_area()          # Update summary
        print("Display Updated!")
        print("Supply Components: ", [c.name for c in self.ahu.components])
        print("Return Components: ", [c.name for c in self.ahu.return_components])

    def handle_add_component(self, comp_name):
        size = self.ahu.model_size
        if size is None:
            print("Invalid CFM")
            return
        try:
            # In dual mode, add to supply by default; user can drag to return
            self.ahu.add_component(comp_name, size, side="supply")
            self.update_display()
        except KeyError:
            print(f"Size {size} not found for {comp_name}")




def run_gui(json_path="ahu_components.json"):
    with open(json_path) as read_file:
        components_dict = json.load(read_file)

    ahu = AHU(components_dict)

    root = tk.Tk()
    app = AHUGUI(root, ahu)
    root.geometry("1200x700")
    root.mainloop()




if __name__ == "__main__":
    run_gui()
