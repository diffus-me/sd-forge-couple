from PIL import Image
import gradio as gr
import numpy as np

from .gr_version import js, is_gradio_4
from .ui_funcs import COLORS


class CoupleMaskData:

    def __init__(self, is_img2img: bool):
        self.mode: str = "i2i" if is_img2img else "t2i"
        self.masks: list[Image.Image] = []
        self.weights: list[float] = []

        self.selected_index: int = -1

    def get_masks(self) -> list[dict]:
        count = len(self.masks)
        assert count == len(self.weights)

        if count == 0:
            return None

        return [
            {"mask": self.masks[i], "weight": self.weights[i]} for i in range(count)
        ]

    def mask_ui(self, *args):
        return self._mask_ui_4(*args) if is_gradio_4 else self._mask_ui_3(*args)

    def _mask_ui_3(self, btn, res, mode) -> list[gr.components.Component]:
        """The UI for the "Classic" Forge based on Gradio 3.x"""

        # ===== Components ===== #
        msk_btn_empty = gr.Button("Create Empty Canvas", elem_classes="round-btn")

        gr.HTML(
            """
            <h2 align="center"><ins>Mask Canvas</ins></h2>
            <p align="center"><b>[Important]</b> Do <b>NOT</b> upload / paste an image to here...</p>
            """
        )

        msk_canvas = gr.Image(
            show_label=False,
            source="upload",
            interactive=True,
            type="pil",
            tool="color-sketch",
            image_mode="RGB",
            brush_color="#ffffff",
            elem_classes="fc_msk_canvas",
        )

        gr.HTML(
            """
            <p align="center">
            <sub>Adjust the brush size if you cannot see the cursor...</sub><br>
            <sup><s>Blame Gradio</s></sup>
            </p>
            """
        )

        with gr.Row(elem_classes="fc_msk_io"):
            msk_btn_save = gr.Button(
                "Save Mask ", interactive=True, elem_classes="round-btn"
            )
            msk_btn_load = gr.Button(
                "Load Mask", interactive=False, elem_classes="round-btn"
            )
            msk_btn_override = gr.Button(
                "Override Mask", interactive=False, elem_classes="round-btn"
            )

        with gr.Row(visible=False):
            operation = gr.Textbox(interactive=True, elem_classes="fc_msk_op")
            operation_btn = gr.Button("op", elem_classes="fc_msk_op_btn")

        gr.HTML('<div class="fc_masks"></div>')

        gr.HTML('<h2 align="center"><ins>Mask Preview</ins></h2>')

        msk_preview = gr.Image(
            show_label=False,
            image_mode="RGB",
            type="pil",
            interactive=False,
            show_download_button=False,
            elem_classes="fc_msk_preview",
        )

        msk_gallery = gr.Gallery(
            show_label=False,
            show_share_button=False,
            show_download_button=False,
            interactive=False,
            visible=False,
            elem_classes="fc_msk_gal",
        )

        msk_btn_reset = gr.Button("Reset All Masks", elem_classes="round-btn")

        weights_field = gr.Textbox(visible=False, elem_classes="fc_msk_weights")
        # ===== Components ===== #

        # ===== Events ===== #
        msk_canvas.change(
            fn=None, **js(f'() => {{ ForgeCouple.hideButtons("{self.mode}"); }}')
        )

        msk_btn_empty.click(self._create_empty, res, msk_canvas)

        msk_btn_save.click(
            self._write_mask,
            msk_canvas,
            [msk_gallery, msk_preview, msk_btn_load, msk_btn_override],
        ).success(
            fn=None, **js(f'() => {{ ForgeCouple.populateMasks("{self.mode}"); }}')
        )

        msk_btn_override.click(
            self._override_mask,
            msk_canvas,
            [msk_gallery, msk_preview, msk_btn_load, msk_btn_override],
        ).success(
            fn=None, **js(f'() => {{ ForgeCouple.populateMasks("{self.mode}"); }}')
        )

        msk_btn_load.click(self._load_mask, None, msk_canvas)

        msk_btn_reset.click(
            self._reset_masks,
            None,
            [msk_gallery, msk_preview, msk_btn_load, msk_btn_override],
        ).success(
            fn=None, **js(f'() => {{ ForgeCouple.populateMasks("{self.mode}"); }}')
        )

        weights_field.change(self._write_weights, weights_field)

        operation_btn.click(
            self._on_operation,
            operation,
            [msk_gallery, msk_preview, msk_btn_load, msk_btn_override],
        ).success(
            fn=None, **js(f'() => {{ ForgeCouple.populateMasks("{self.mode}"); }}')
        )

        btn.click(
            self._refresh_resolution,
            [res, mode],
            [msk_gallery, msk_preview, msk_canvas],
        ).success(
            fn=None, **js(f'() => {{ ForgeCouple.populateMasks("{self.mode}"); }}')
        )
        # ===== Events ===== #

        # ===== Pain ===== #
        [
            setattr(comp, "do_not_save_to_config", True)
            for comp in (
                msk_btn_empty,
                msk_canvas,
                msk_btn_save,
                msk_btn_load,
                msk_btn_override,
                operation,
                operation_btn,
                msk_preview,
                msk_gallery,
                msk_btn_reset,
                weights_field,
            )
        ]

    def _mask_ui_4(self, btn, res, mode) -> list[gr.components.Component]:
        """The UI for the "Neo" Forge based on Gradio 4.x"""
        raise NotImplementedError

    @staticmethod
    def _parse_resolution(resolution: str) -> tuple[int, int]:
        """Convert the resolution from width and height slider"""
        w, h = [int(v) for v in resolution.split("x")]
        while w * h > 1024 * 1024:
            w //= 2
            h //= 2

        return (w, h)

    @staticmethod
    def _create_empty(resolution: str) -> Image.Image:
        """Generate a blank black canvas"""
        w, h = CoupleMaskData._parse_resolution(resolution)
        return Image.new("RGB", (w, h))

    def _on_operation(self, op: str) -> list[list, Image.Image, bool, bool]:
        """Operations triggered from JavaScript"""
        self.selected_index = -1
        mask_update: bool = True

        # Reorder
        if "=" in op:
            from_id, to_id = [int(v) for v in op.split("=")]
            self.masks[from_id], self.masks[to_id] = (
                self.masks[to_id],
                self.masks[from_id],
            )

        # Delete
        elif "-" in op:
            to_del = int(op.split("-")[1])
            del self.masks[to_del]

        # Select
        else:
            self.selected_index = int(op.strip())
            mask_update = False

        return [
            self.masks if mask_update else gr.update(),
            self._generate_preview() if mask_update else gr.update(),
            gr.update(interactive=(self.selected_index >= 0)),
            gr.update(interactive=(self.selected_index >= 0)),
        ]

    def _generate_preview(self) -> Image.Image:
        """Create a preview based on cached masks"""
        if not self.masks:
            return None

        res: tuple[int, int] = self.masks[0].size
        bg = Image.new("RGBA", res, "black")

        for i, mask in enumerate(self.masks):
            color = Image.new("RGB", res, COLORS[i % 7])
            alpha = Image.fromarray(np.asarray(mask).astype(np.uint8) * 144)
            rgba = Image.merge("RGBA", [*color.split(), alpha.convert("L")])
            bg.paste(rgba, (0, 0), rgba)

        return bg

    def _refresh_resolution(
        self, resolution: str, mode: str
    ) -> list[list, Image.Image, Image.Image]:
        """Refresh when width or height is changed"""
        canvas = self._create_empty(resolution)

        if mode != "Mask" or not self.masks:
            return [gr.update(), gr.update(), canvas]

        w, h = self._parse_resolution(resolution)

        self.masks = [mask.resize((w, h)) for mask in self.masks]
        preview = self._generate_preview()
        return [self.masks, preview, canvas]

    def _reset_masks(self) -> list[list, Image.Image, bool, bool]:
        """Clear everything"""
        self.masks.clear()
        self.weights.clear()
        preview = self._generate_preview()

        return [
            self.masks,
            preview,
            gr.update(interactive=False),
            gr.update(interactive=False),
        ]

    def _load_mask(self) -> Image.Image:
        """Load a cached mask to canvas based on index"""
        return self.masks[self.selected_index]

    def _override_mask(
        self, img: None | Image.Image
    ) -> list[list, Image.Image, bool, bool]:
        """Override a cached mask based on index"""
        if img is None:
            self.selected_index = -1
            return [
                self.masks,
                gr.update(),
                gr.update(interactive=False),
                gr.update(interactive=False),
            ]

        assert isinstance(img, Image.Image)

        if not bool(img.getbbox()):
            self.selected_index = -1
            return [
                self.masks,
                gr.update(),
                gr.update(interactive=False),
                gr.update(interactive=False),
            ]

        self.masks[self.selected_index] = img.convert("1")
        self.selected_index = -1

        preview = self._generate_preview()
        return [
            self.masks,
            preview,
            gr.update(interactive=False),
            gr.update(interactive=False),
        ]

    def _write_mask(
        self, img: None | Image.Image
    ) -> list[list, Image.Image, bool, bool]:
        """Save a new mask"""
        if img is None:
            return [
                self.masks,
                gr.update(),
                gr.update(interactive=False),
                gr.update(interactive=False),
            ]

        assert isinstance(img, Image.Image)

        if not bool(img.getbbox()):
            return [
                self.masks,
                gr.update(),
                gr.update(interactive=False),
                gr.update(interactive=False),
            ]

        self.masks.append(img.convert("1"))

        preview = self._generate_preview()
        return [
            self.masks,
            preview,
            gr.update(interactive=False),
            gr.update(interactive=False),
        ]

    def _write_weights(self, weights: str):
        """Cache the mask weights"""
        if not weights.strip():
            self.weights = []
        else:
            self.weights = [float(v) for v in weights.split(",")]
