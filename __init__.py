bl_info = {
    "name": "Outliner Icon Example",
    "author": "Kk-Infinite",
    "version": (2, 0, 0),
    "blender": (4, 1, 1),
    "location": "View3D > Sidebar > Outliner Icon",
    "description": "Example consumer for the standalone Outliner icon bridge",
    "category": "Object",
}

import random

import bpy
from bpy.app.handlers import persistent

from .outliner_icon_runtime import OutlinerIconBridge, bundled_asset_path


EXAMPLE_COLLECTION_NAME = "Outliner Icon Example"
TAG_KEY = "outliner_icon_example_kind"
ASSET_KEY = "outliner_icon_example_asset"
CUSTOM_ICON_KIND = "CUSTOM_ICON"
ICON_ASSETS = (
    "test_icon_01",
    "test_icon_02",
    "test_icon_03",
    "test_icon_04",
    "icon_flower",
    "icon_cloud",
    "icon_smile",
    "icon_wink",
    "icon_ufo",
    "icon_coffee",
)
BRIDGE = OutlinerIconBridge()


def register_example_assets():
    for asset_key in ICON_ASSETS:
        BRIDGE.register_asset(asset_key, bundled_asset_path(asset_key + ".png"))


def iter_example_bindings():
    for obj in bpy.data.objects:
        if obj.get(TAG_KEY) == CUSTOM_ICON_KIND:
            asset_key = obj.get(ASSET_KEY)
            if asset_key in ICON_ASSETS:
                yield obj, asset_key


@persistent
def rebind_example_icons(_):
    register_example_assets()
    BRIDGE.rebind(iter_example_bindings())


def delayed_rebind_example_icons():
    try:
        rebind_example_icons(None)
    except AttributeError:
        return 0.25
    return None


def ensure_collection(name, parent=None):
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
    if parent is not None and parent.children.get(collection.name) is None:
        parent.children.link(collection)
    return collection


def random_object_name():
    while True:
        name = "Icon Example " + str(random.SystemRandom().randint(100000, 999999))
        if bpy.data.objects.get(name) is None:
            return name


class OUTLINERICON_OT_create_example(bpy.types.Operator):
    bl_idname = "outliner_icon_example.create"
    bl_label = "Create Icon Examples"
    bl_options = {'REGISTER', 'UNDO'}

    count: bpy.props.IntProperty(name="Count", default=5, min=1, max=20)

    def execute(self, context):
        collection = ensure_collection(EXAMPLE_COLLECTION_NAME, context.scene.collection)
        created = []
        for index in range(self.count):
            obj = bpy.data.objects.new(random_object_name(), None)
            obj.empty_display_type = "PLAIN_AXES"
            obj.location = (float(index) * 2.0, 0.0, 0.0)
            obj[TAG_KEY] = CUSTOM_ICON_KIND
            obj[ASSET_KEY] = random.choice(ICON_ASSETS)
            collection.objects.link(obj)
            BRIDGE.bind(obj, obj[ASSET_KEY])
            created.append(obj)
        BRIDGE.redraw_outliners()
        context.view_layer.objects.active = created[-1]
        created[-1].select_set(True)
        self.report({'INFO'}, "Created " + str(self.count) + " icon examples")
        return {'FINISHED'}


class OUTLINERICON_OT_randomize_active_icon(bpy.types.Operator):
    bl_idname = "outliner_icon_example.randomize_active_icon"
    bl_label = "Randomize Active Object Icon"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        obj = context.active_object
        register_example_assets()
        previous_asset = obj.get(ASSET_KEY)
        choices = tuple(asset for asset in ICON_ASSETS if asset != previous_asset)
        asset_key = random.choice(choices or ICON_ASSETS)
        obj[TAG_KEY] = CUSTOM_ICON_KIND
        obj[ASSET_KEY] = asset_key

        if not BRIDGE.bind(obj, asset_key):
            self.report({'ERROR'}, "Icon binding failed: " + BRIDGE.error)
            return {'CANCELLED'}

        BRIDGE.redraw_outliners()
        self.report({'INFO'}, "Assigned " + asset_key + " to " + obj.name)
        return {'FINISHED'}


class OUTLINERICON_PT_panel(bpy.types.Panel):
    bl_label = "Outliner Icon Example"
    bl_idname = "OUTLINERICON_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Outliner Icon"

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.prop(context.scene, "outliner_icon_example_count", text="")
        operator = row.operator(OUTLINERICON_OT_create_example.bl_idname, icon='OUTLINER')
        operator.count = context.scene.outliner_icon_example_count
        layout.separator()
        active_object = context.active_object
        if active_object is None:
            layout.label(text="Select an object to replace its icon", icon='INFO')
        else:
            layout.label(text="Active: " + active_object.name, icon='OBJECT_DATA')
            layout.operator(
                OUTLINERICON_OT_randomize_active_icon.bl_idname,
                icon='FILE_REFRESH',
            )
        diagnostics = BRIDGE.diagnostics()
        layout.separator()
        layout.label(text="Native hook: " + ("ready" if diagnostics.ready else "not loaded"))
        layout.label(text="Hook: " + diagnostics.error[:52])
        layout.label(text=f"maps={diagnostics.mappings} calls={diagnostics.calls}")
        layout.label(text=f"overrides={diagnostics.overrides}")


CLASSES = (
    OUTLINERICON_OT_create_example,
    OUTLINERICON_OT_randomize_active_icon,
    OUTLINERICON_PT_panel,
)


def register():
    bpy.types.Scene.outliner_icon_example_count = bpy.props.IntProperty(default=5, min=1, max=20)
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    if rebind_example_icons not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(rebind_example_icons)
    if rebind_example_icons not in bpy.app.handlers.undo_post:
        bpy.app.handlers.undo_post.append(rebind_example_icons)
    if rebind_example_icons not in bpy.app.handlers.redo_post:
        bpy.app.handlers.redo_post.append(rebind_example_icons)
    bpy.app.timers.register(delayed_rebind_example_icons, first_interval=0.1)


def unregister():
    if rebind_example_icons in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(rebind_example_icons)
    if rebind_example_icons in bpy.app.handlers.undo_post:
        bpy.app.handlers.undo_post.remove(rebind_example_icons)
    if rebind_example_icons in bpy.app.handlers.redo_post:
        bpy.app.handlers.redo_post.remove(rebind_example_icons)
    BRIDGE.close()
    del bpy.types.Scene.outliner_icon_example_count
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
