import argparse,sys
sys.path.insert(0,"/")
from robot_client import call
p=argparse.ArgumentParser()
for key in ("x","y","z"):p.add_argument("--"+key,type=float,required=True)
a=p.parse_args()
print(call("command",{"kind":"position_grasp","parameters":vars(a)}))
