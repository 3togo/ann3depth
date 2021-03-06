"""
Converts all data to the same dimensions and into the same formats.

Skips and reports broken data.

The variables WIDTH, HEIGHT, D_WIDTH, D_HEIGHT control the image and depth map
dimensions. The variables START and LIMIT describe the range of samples to
convert and default to "all".

Careful! Currently all methods don't test if they match the correct depth and
images, but make the assumption that they always follow the same name scheme and
are thus ordered!
"""
import os
import shutil
import sys

import h5py

import numpy as np
import scipy.io as sio
import scipy.misc as smisc

WIDTH = int(os.environ.get('WIDTH', 640))
HEIGHT = int(os.environ.get('HEIGHT', 480))
D_HEIGHT = int(os.environ.get('DHEIGHT', 55))
D_WIDTH = int(os.environ.get('DWIDTH', D_HEIGHT * WIDTH // HEIGHT))

START = int(os.environ.get('START', 0))
try:
    LIMIT = int(os.environ.get('LIMIT'))
except ValueError:
    LIMIT = None


def include(img):
    """Filter to remove files which are not part of the datasets."""
    return img[img.index('.') + 1:] not in ['txt', 'db']


def __empty_dirs_or_fail(directories):
    """If the environment variable FORCE is set to a value which evaluates to
    True, the directories are emptied. Otherwise this function checks whether
    the directories are empty or not, and if not, it raises a FileExistsError.

    Args:
        directories: directories to check.

    Raises:
        FileExistsError if directory is not empty and environment FORCE is not
        set to True.
    """
    if os.environ.get('FORCE'):
        for directory in directories:
            files = os.listdir(directory)
            for f in files:
                os.remove(os.path.join(directory, f))
        return
    for directory in directories:
        if os.listdir(directory) != []:
            msg = f'Directory is not empty: {directory}, aborting... Use FORCE=1!'
            raise FileExistsError(msg)


def __process_make3d1(path_train, path_test):
    """Converts data of make3d1."""
    print(f'Images: {WIDTH}x{HEIGHT} Depths: {D_WIDTH}x{D_HEIGHT}')

    path = os.path.join(os.environ['DATA_DIR'], 'make3d1', 'unpacked')
    depth_path = [os.path.join(path, d) for d in ['Train400Depth',
                                                  'Test134Depth']]
    img_path = [os.path.join(path, d) for d in ['Train400Img',
                                                'Test134']]

    target_path = [path_train, path_test]

    __empty_dirs_or_fail(target_path)

    for dp, ip, tp in zip(depth_path, img_path, target_path):
        print(f'Preprocessing images in {dp} and {ip}')

        depths = list(filter(include, os.listdir(dp)))
        imgs = list(filter(include, os.listdir(ip)))

        c = START
        for d, i in zip(depths[START:LIMIT], imgs[START:LIMIT]):
            try:
                name = d[d.index('-') + 1:d.index('.')]

                img = smisc.imread(os.path.join(ip, i))
                img = smisc.imresize(img, (WIDTH, HEIGHT))

                depth = sio.loadmat(os.path.join(dp, d))
                depth = depth['Position3DGrid'][..., 3]

                depth = smisc.imresize(depth, (D_WIDTH, D_HEIGHT))
            except ValueError as ve:
                print(f'Skipping sample {c}, {d} and {i}. Reason: {ve}')
                continue
            c += 1

            smisc.imsave(os.path.join(tp, f'{name}-image.png'), img)
            smisc.imsave(os.path.join(tp, f'{name}-depth.png'), depth)


def __process_make3d2(path_train, path_test):
    """Converts data of make3d2. Needs to perform a rotation."""
    print(f'Images: {WIDTH}x{HEIGHT} Depths: {D_WIDTH}x{D_HEIGHT}')

    path = os.path.join(os.environ['DATA_DIR'], 'make3d2', 'unpacked')

    depth_path = [os.path.join(path, d) for d in ['Dataset3_Depths',
                                                  'Dataset2_Depths']]
    img_path = [os.path.join(path, d) for d in ['Dataset3_Images',
                                                'Dataset2_Images']]
    target_path = [path_train, path_test]

    __empty_dirs_or_fail(target_path)

    for dp, ip, tp in zip(depth_path, img_path, target_path):
        print(f'Preprocessing images in {dp} and {ip}')

        depths = list(filter(include, os.listdir(dp)))
        imgs = list(filter(include, os.listdir(ip)))

        c = START
        for d, i in zip(depths[START:LIMIT], imgs[START:LIMIT]):
            try:
                name = d[d.index('-') + 1:d.index('.')]

                img = smisc.imread(os.path.join(ip, i))
                img = np.rot90(img, k=-1)
                img = smisc.imresize(img, (WIDTH, HEIGHT))

                depth = sio.loadmat(os.path.join(dp, d))['depthMap']
                depth = smisc.imresize(depth, (D_WIDTH, D_HEIGHT))
            except ValueError as ve:
                print(f'Skipping sample {c}, {d} and {i}. Reason: {ve}')
                continue
            c += 1

            smisc.imsave(os.path.join(tp, f'{name}-image.png'), img)
            smisc.imsave(os.path.join(tp, f'{name}-depth.png'), depth)


def __process_mnist(path_train, path_test):
    """Moves the mnist files to the proper directory."""
    target_path = [path_train, path_test]

    __empty_dirs_or_fail(target_path)

    path = os.path.join(os.environ['DATA_DIR'], 'mnist', 'unpacked')
    train_prefix = 'train-'
    test_prefix = 't10k-'
    for fn in os.listdir(path):
        if fn.startswith(train_prefix):
            goal = path_train
        elif fn.startswith(test_prefix):
            goal = path_test
        else:
            print(f'Skipping {fn}')
            continue
        print(f'Moving {fn}')
        shutil.move(os.path.join(path, fn), goal)


def __process_nyu(path_train, path_test):
    """Converts data of nyu. Extracts data from single mat file.
    Rotates images by 90 degrees clock-wise."""
    print(f'Images: {WIDTH}x{HEIGHT} Depths: {D_WIDTH}x{D_HEIGHT}')

    target_path = [path_train, path_test]

    train_images = 5

    path = os.path.join(os.environ['DATA_DIR'], 'nyu', 'unpacked',
                        'nyu_depth_v2_labeled.mat')

    __empty_dirs_or_fail(target_path)

    c = 0
    with h5py.File(path) as mat:
        for d, i, n in zip(mat['depths'],
                           mat['images'],
                           mat['rawRgbFilenames'][0]):
            if c < START:
                c += 1
                continue

            if LIMIT and c >= LIMIT:
                break

            img = smisc.imresize(i, (WIDTH, HEIGHT))
            img = np.rot90(img, k=-1)
            depth = smisc.imresize(d, (D_WIDTH, D_HEIGHT))
            depth = np.rot90(depth, k=-1)

            try:
                name = (''.join(map(chr, mat[n][:].T[0]))
                        .replace('/', '_')
                        .replace('.', '_'))[:-4]
            except TypeError as te:
                print(f'Skipping sample {c}. Reason: {te}')

            smisc.imsave(os.path.join(target_path[0 if c % train_images else 1],
                                      f'{name}-image.png'), img)
            smisc.imsave(os.path.join(target_path[0 if c % train_images else 1],
                                      f'{name}-depth.png'), depth)

            c += 1


def main():
    """Creates directories per dataset in data/train and data/test. Then
    converts all data matching keys in sys.argv to the requested sizes and
    stores all as png files. If no key is provided it tries to processes
    all datasets."""
    processors = {
        'make3d1': __process_make3d1,
        'make3d2': __process_make3d2,
        'nyu': __process_nyu,
        'mnist': __process_mnist,
    }

    print('\nPreprocessing data...')
    for key, processor in processors.items():
        train = os.path.join(os.environ['DATA_DIR'], key, 'train')
        test = os.path.join(os.environ['DATA_DIR'], key, 'test')
        try:
            if key in sys.argv or len(sys.argv) == 1:
                try:
                    os.makedirs(train, 0o755)
                    os.makedirs(test, 0o755)
                except OSError:
                    pass
                print(f'Preprocessing {key}')
                processor(train, test)
        except FileExistsError as fe:
            print(fe)
    print('Preprocessing done.')


if __name__ == '__main__':
    main()
