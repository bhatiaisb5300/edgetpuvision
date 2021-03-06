"""A demo which runs object detection on camera frames."""

# export TEST_DATA=/usr/lib/python3/dist-packages/edgetpu/test_data
#
# Run face detection model:
# python3 -m edgetpuvision.detect \
#   --model ${TEST_DATA}/mobilenet_ssd_v2_face_quant_postprocess_edgetpu.tflite
#
# Run coco model:
# python3 -m edgetpuvision.detect \
#   --model ${TEST_DATA}/mobilenet_ssd_v2_coco_quant_postprocess_edgetpu.tflite \
#   --labels ${TEST_DATA}/coco_labels.txt

import argparse
import collections
import colorsys
import itertools
import time

from collections import deque

from edgetpu.detection.engine import BasicEngine

import svg
import utils
from apps import run_app

import numpy as np
from PIL import Image

# from pycoral.adapters import common
# from pycoral.adapters import segment
# from pycoral.utils.edgetpu import make_interpreter

CSS_STYLES = str(svg.CssStyle({'.back': svg.Style(fill='black',
                                                  stroke='black',
                                                  stroke_width='1em'),
                               '.bbox': svg.Style(fill_opacity=0.0,
                                                  stroke_width='2px')}))

# BBox = collections.namedtuple('BBox', ('x', 'y', 'w', 'h'))
# BBox.area = lambda self: self.w * self.h
# BBox.scale = lambda self, sx, sy: BBox(x=self.x * sx, y=self.y * sy,
#                                        w=self.w * sx, h=self.h * sy)
# BBox.__str__ = lambda self: 'BBox(x=%.2f y=%.2f w=%.2f h=%.2f)' % self
#
# Object = collections.namedtuple('Object', ('id', 'label', 'score', 'bbox'))
# Object.__str__ = lambda self: 'Object(id=%d, label=%s, score=%.2f, %s)' % self

centerPts = deque(maxlen=30)

def size_em(length):
    return '%sem' % str(0.6 * length)

def color(i, total):
    return tuple(int(255.0 * c) for c in colorsys.hsv_to_rgb(i / total, 1.0, 1.0))

def make_palette(keys):
    return {key : svg.rgb(color(i, len(keys))) for i, key in enumerate(keys)}

def make_get_color(color, labels):
    if color:
        return lambda obj_id: color

    if labels:
        palette = make_palette(labels.keys())
        return lambda obj_id: palette[obj_id]

    return lambda obj_id: 'white'

def overlay(title, result, inference_time, inference_rate, layout):
    x0, y0, width, height = layout.window

    defs = svg.Defs()
    defs += CSS_STYLES

    doc = svg.Svg(width=width, height=height,
                  viewBox='%s %s %s %s' % layout.window,
                  font_size='1em', font_family='monospace', font_weight=500)
    doc += defs

    ox1, ox2 = x0 + 20, x0 + width - 20
    oy1, oy2 = y0 + 20, y0 + height - 20
    # Title
    if title:
        doc += svg.Rect(x=ox, y=oy1,
                        width=size_em(len(title)), height='1em',
                        _class='back')
        t = svg.Text(x=ox, y=oy1, fill='white')
        t += svg.TSpan(title, dy='1em')
        doc +=t

    # Info
    lines = [
        # 'Objects: %d' % len(objs),
        'Inference time: %.2f ms (%.2f fps)' % (inference_time * 1000, 1.0 / inference_time)
    ]
    # text_width = size_em(max(len(line) for line in lines))
    doc += svg.Rect(x=0, y=0, height='2.2em',
                    transform='translate(%s, %s) scale(1,-1)' % (ox, oy2), _class='back')
    t = svg.Text(y=oy2, fill='white')
    # t += svg.TSpan(lines[0], x=ox)
    # t += svg.TSpan(lines[1], x=ox, dy='-1.2em')
    doc += t

    return str(doc)


# def convert(obj, labels):
#     x0, y0, x1, y1 = obj.bounding_box.flatten().tolist()
#     return Object(id=obj.label_id,
#                   label=labels[obj.label_id] if labels else None,
#                   score=obj.score,
#                   bbox=BBox(x=x0, y=y0, w=x1 - x0, h=y1 - y0))

# def print_results(inference_rate, objs):
#     print('\nInference (rate=%.2f fps):' % inference_rate)
#     for i, obj in enumerate(objs):
#         print('    %d: %s, area=%.2f' % (i, obj, obj.bbox.area()))


#segeemetation starts here
def create_pascal_label_colormap():
  """Creates a label colormap used in PASCAL VOC segmentation benchmark.
  Returns:
    A Colormap for visualizing segmentation results.
  """
  colormap = np.zeros((256, 3), dtype=int)
  indices = np.arange(256, dtype=int)

  for shift in reversed(range(8)):
    for channel in range(3):
      colormap[:, channel] |= ((indices >> channel) & 1) << shift
    indices >>= 3

  return colormap

def label_to_color_image(label):
  """Adds color defined by the dataset colormap to the label.
  Args:
    label: A 2D array with integer type, storing the segmentation label.
  Returns:
    result: A 2D array with floating type. The element of the array
      is the color indexed by the corresponding element in the input label
      to the PASCAL color map.
  Raises:
    ValueError: If label is not of rank 2 or its value is larger than color
      map maximum entry.
  """
  if label.ndim != 2:
    raise ValueError('Expect 2-D input label')

  colormap = create_pascal_label_colormap()

  if np.max(label) >= len(colormap):
    raise ValueError('label value too large.')

  return colormap[label]


def render_gen(args):
    fps_counter  = utils.avg_fps_counter(30)

    engines, titles = utils.make_engines(args.model, BasicEngine)
    assert utils.same_input_image_sizes(engines)
    engines = itertools.cycle(engines)
    engine = next(engines)

    # labels = utils.load_labels(args.labels) if args.labels else None
    # filtered_labels = set(l.strip() for l in args.filter.split(',')) if args.filter else None
    # get_color = make_get_color(args.color, labels)
    # _, height, width, _ = engine.get_input_tensor_shape()
    draw_overlay = True
    #
    yield utils.input_image_size(engine)
    #
    output = None
    while True:
        tensor, layout, command = (yield output)
    #
        inference_rate = next(fps_counter)
        if draw_overlay:
            start = time.monotonic()
            _, raw_result = engine.run_inference(tensor)
            inference_time = time.monotonic() - start
            result = np.reshape(raw_result, (height, width))    #
            if args.print:
                print_results(inference_rate, objs)
    #
            title = titles[engine]
            output = overlay(title, result, inference_time, inference_rate, layout)
        else:
            output = None
    #
        if command == 'o':
            draw_overlay = not draw_overlay
        elif command == 'n':
            engine = next(engines)

    # interpreter = make_interpreter(args.model, device=':0')
    # interpreter.allocate_tensors()
    # width, height = common.input_size(interpreter)
    #
    # img = Image.open(args.input)
    # if args.keep_aspect_ratio:
    # resized_img, _ = common.set_resized_input(
    #     interpreter, img.size, lambda size: img.resize(size, Image.ANTIALIAS))
    # else:
    # resized_img = img.resize((width, height), Image.ANTIALIAS)
    # common.set_input(interpreter, resized_img)
    #
    # interpreter.invoke()
    # result = segment.get_output(interpreter)

def add_render_gen_args(parser):
    parser.add_argument('--model', required=True,
                      help='Path of the segmentation model.')
    # parser.add_argument('--input', required=True,
    #                   help='File path of the input image.')
    # parser.add_argument('--output', default='semantic_segmentation_result.jpg',
    #                   help='File path of the output image.')
    parser.add_argument(
      '--keep_aspect_ratio',
      action='store_true',
      default=False,
      help=(
          'keep the image aspect ratio when down-sampling the image by adding '
          'black pixel padding (zeros) on bottom or right. '
          'By default the image is resized and reshaped without cropping. This '
          'option should be the same as what is applied on input images during '
          'model training. Otherwise the accuracy may be affected and the '
          'bounding box of detection result may be stretched.'))

def main():
    run_app(add_render_gen_args, render_gen)

if __name__ == '__main__':
    main()
