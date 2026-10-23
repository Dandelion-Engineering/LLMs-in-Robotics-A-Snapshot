"""Public six-face pigment calibration. Inputs are rendered RGB-D only."""
import copy
import sensor_worker

inherited_detector = sensor_worker.derive_detections

def derive_detections(rgb, depth, calibration, registry, zones, zone_halves):
    tags=copy.deepcopy(registry)
    if 'C1' in tags and 'side_face_hue' in tags['C1']:
        side=copy.deepcopy(tags['C1'])
        side['hue']=side['side_face_hue'];side['half'][2]=side['side_face_half_height_m']
        tags['C1_side_face']=side
    detections=inherited_detector(rgb,depth,calibration,tags,zones,zone_halves)
    faces=[d for d in detections if d['id'] in ('C1','C1_side_face')]
    ordinary=[d for d in detections if d['id'] not in ('C1','C1_side_face')]
    if faces:
        chosen=max(faces,key=lambda d:d['pixels'])
        chosen['id']='C1';ordinary.append(chosen)
    return ordinary

sensor_worker.derive_detections=derive_detections
