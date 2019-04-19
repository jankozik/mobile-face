import os, sys
import argparse
import cv2
import dlib
import time
from mxnet import nd
sys.path.append(os.path.abspath(os.path.dirname(__file__)) + os.sep + '../MobileFace_Detection/')
from mobileface_detector import MobileFaceDetection
sys.path.append(os.path.abspath(os.path.dirname(__file__)) + os.sep + '../MobileFace_Align/')
from mobileface_alignment import MobileFaceAlign
sys.path.append(os.path.abspath(os.path.dirname(__file__)) + os.sep + '../MobileFace_Attribute/')
from mobileface_attribute_predictor import MobileFaceAttribute

def parse_args():
    parser = argparse.ArgumentParser(description='Test MobileFace networks.')
    parser.add_argument('--model_detect', type=str, 
                        default='../MobileFace_Detection/model/mobilefacedet_v1_gluoncv.params',
                        help="Pretrained detection model path.")
    parser.add_argument('--model_landmark', type=str,
                        default='../MobileFace_Landmark/mobileface_landmark_emnme_v1.dat',
                        help='Pretrained landmark model path.')
    parser.add_argument('--model_align', type=str,
                        default='../MobileFace_Align/mobileface_align_v1.npy',
                        help='Align model params path.')
    parser.add_argument('--model_attribute', type=str, 
                        default='../MobileFace_Attribute/model/mobileface_attr_v1_gluoncv.params',
                        help="Pretrained attribute model path.")
    parser.add_argument('--images', type=str, default='./friends.jpg',
                        help='Test images, use comma to split multiple.')
    parser.add_argument('--gpus', type=str, default='',
                        help='Default is cpu , you can specify 1,3 for example with GPUs.')
    parser.add_argument('--pretrained', type=str, default='True',
                        help='Load weights from previously saved parameters.')
    parser.add_argument('--thresh', type=float, default=0.5,
                        help='Threshold of object score when visualize the bboxes.')
    args = parser.parse_args()
    return args

def main():
    args = parse_args() 
    landmark_num = 5 # the version of v1 support 5 or 3 now
    align_size = (96, 96) # the face image size after alined
    bboxes_predictor = MobileFaceDetection(args.model_detect, args.gpus)
    landmark_predictor = dlib.shape_predictor(args.model_landmark)
    attr_predictor = MobileFaceAttribute(args.model_attribute, args.gpus)
    align_tool = MobileFaceAlign(args.model_align)
    image_list = [x.strip() for x in args.images.split(',') if x.strip()]
    for img_dir in image_list:
        img_mat = cv2.imread(img_dir)
        results = bboxes_predictor.mobileface_detector(img_dir, img_mat)
        if results == None or len(results) < 1:
            continue
            
        for i, result in enumerate(results):
            xmin, ymin, xmax, ymax, score, classname = result
            # The landmarks predictor is not trained with union the detector of the mobilefacedet above. 
            # Therefore, we need to make some adjustments to the original detection results 
            # to adapt to the landmarks predictor. 
            size_scale = 0.75
            center_scale = 0.1
            center_shift = (ymax - ymin) * center_scale
            w_new = (ymax - ymin) * size_scale
            h_new = (ymax - ymin) * size_scale
            x_center = xmin + (xmax - xmin) / 2
            y_center = ymin + (ymax - ymin) / 2 + center_shift
            x_min = int(x_center - w_new / 2)
            y_min = int(y_center - h_new / 2)
            x_max = int(x_center + w_new / 2)
            y_max = int(y_center + h_new / 2)

            dlib_box = dlib.rectangle(x_min, y_min, x_max, y_max)

            tic = time.time()
            shape = landmark_predictor(img_mat, dlib_box)
            toc = time.time() - tic
            print('Landmark predict time: %fms' % (toc*1000))

            points = []
            for k in range(landmark_num):
                points.append([shape.part(k).x, shape.part(k).y])

            align_points = []
            align_points.append(points)
            tic = time.time()
            align_result = align_tool.get_align(img_mat, align_points, align_size)
            toc = time.time() - tic
            print('Face align time: %fms' % (toc*1000))
            save_aligned = './align_result/' + str(i) + '.jpg'
            cv2.imwrite(save_aligned, align_result[0])

            align_rgb = cv2.cvtColor(align_result[0], cv2.COLOR_BGR2RGB)
            img_nd = nd.array(align_rgb)
            tic = time.time()
            attr_result = attr_predictor.get_attribute(img_nd)
            toc = time.time() - tic
            print('Attribute predict time: %fms' % (toc*1000))

            # plot detection
            cv2.rectangle(img_mat, (x_min, y_min), (x_max, y_max), (0,255,0), 3)
            cv2.putText(img_mat, str('%s%0.2f' % (classname, score)), 
                       (x_min, y_min - 5), cv2.FONT_HERSHEY_COMPLEX , 0.7, (0,0,255), 2)
            # plot landmarks: 5 points or 3 points
            for k in range(landmark_num):
                cv2.circle(img_mat, (shape.part(k).x, shape.part(k).y), 1, (255,0,0), 2, 8, 0)
            # plot attributes: (gender, age, expression)
            cv2.putText(img_mat, str('%s:%s' % ('g', attr_result[0])), 
                       (x_max + 5, y_min + 10), cv2.FONT_HERSHEY_COMPLEX , 0.5, (216, 128, 0), 2)
            cv2.putText(img_mat, str('%s:%s' % ('a', attr_result[1])), 
                       (x_max + 5, y_min + 30), cv2.FONT_HERSHEY_COMPLEX , 0.5, (216, 128, 0), 2)
            cv2.putText(img_mat, str('%s:%s' % ('e', attr_result[2][0])), 
                       (x_max + 5, y_min + 50), cv2.FONT_HERSHEY_COMPLEX , 0.5, (216, 128, 0), 2)
            cv2.putText(img_mat, str('%s:%s' % (' ', attr_result[2][1])), 
                       (x_max + 5, y_min + 70), cv2.FONT_HERSHEY_COMPLEX , 0.5, (216, 128, 0), 2)            

        cv2.imwrite('result_attribute_v1.jpg', img_mat)
        cv2.imshow('result', img_mat)
        cv2.waitKey(0)

if __name__ == '__main__':
    main()
