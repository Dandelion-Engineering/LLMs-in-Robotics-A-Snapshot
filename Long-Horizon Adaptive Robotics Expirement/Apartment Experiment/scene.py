"""Original procedural MJCF apartment and mobile Cartesian arm. No external assets."""
from xml.sax.saxutils import escape

TOYS = [('red', (.030, .030, .030), '0.9 0.08 0.06 1'),
        ('blue', (.043, .025, .025), '0.08 0.24 0.95 1'),
        ('green', (.026, .037, .035), '0.1 0.75 0.25 1'),
        ('yellow', (.035, .045, .025), '0.95 0.8 0.08 1')]
CHARGERS = [(1.0, 1.0), (5.0, 9.1), (7.0, 1.0)]
DRAWER_CENTERS = ((7.3, 3.5), (8.3, 3.5))

def box(name, pos, size, color, **attrs):
    extra = ' '.join(f'{k}="{escape(str(v))}"' for k, v in attrs.items())
    return f'<geom name="{name}" type="box" pos="{" ".join(map(str,pos))}" size="{" ".join(map(str,size))}" rgba="{color}" {extra}/>'

def container(name, x, y, z, half_x, half_y, height, color):
    return ''.join([box(name+'_floor', (x,y,z), (half_x,half_y,.035), color),
                    box(name+'_n', (x,y+half_y,z+height/2), (half_x,.03,height/2), color),
                    box(name+'_s', (x,y-half_y,z+height/2), (half_x,.03,height/2), color),
                    box(name+'_e', (x+half_x,y,z+height/2), (.03,half_y,height/2), color),
                    box(name+'_w', (x-half_x,y,z+height/2), (.03,half_y,height/2), color)])

def xml():
    props = []
    props.append(box('floor', (6,5,-.10), (6,5,.10), '.78 .76 .70 1'))
    for i,(pos,size) in enumerate([((0,5,1.25),(.08,5,1.25)),((12,5,1.25),(.08,5,1.25)),
                                    ((6,0,1.25),(6,.08,1.25)),((6,10,1.25),(6,.08,1.25)),
                                    ((6,.8,1.25),(.08,.8,1.25)),((6,5,1.25),(.08,1.6,1.25)),
                                    ((6,9.2,1.25),(.08,.8,1.25)),
                                    ((1.05,5,1.25),(1.05,.08,1.25)),((6,5,1.25),(2.1,.08,1.25)),
                                    ((10.95,5,1.25),(1.05,.08,1.25))]):
        props.append(box('wall'+str(i),pos,size,'.88 .87 .82 1', group=1))
    # Bedroom: bed, headboard, pillows, bedside table, chest.
    props += [box('bed_frame',(1.05,8.25,.28),(.85,1.2,.28),'.33 .19 .1 1'),
              box('mattress',(1.05,8.25,.60),(.82,1.16,.10),'.40 .57 .83 1'),
              box('pillow',(1.05,9.05,.74),(.6,.24,.08),'.95 .93 .83 1'),
              box('headboard',(1.05,9.48,.75),(.87,.07,.55),'.33 .19 .1 1'),
              box('nightstand',(2.25,9.1,.35),(.25,.3,.35),'.45 .27 .14 1'),
              container('chest',4.8,8.0,.08,.55,.40,.40,'.65 .40 .16 1')]
    # Living room: couch, TV on stand, low table and throwing bin.
    props += [box('couch_seat',(1,3.7,.38),(.65,1,.20),'.18 .44 .48 1'),
              box('couch_back',(.42,3.7,.80),(.13,1,.50),'.14 .32 .36 1'),
              box('couch_arm1',(1,2.7,.65),(.65,.12,.35),'.14 .32 .36 1'),
              box('couch_arm2',(1,4.7,.65),(.65,.12,.35),'.14 .32 .36 1'),
              box('tvstand',(4.8,4.45,.32),(.8,.30,.32),'.25 .19 .13 1'),
              box('tv',(4.8,4.48,1.08),(.7,.055,.42),'.05 .07 .09 1'),
              box('coffee_table',(2.5,4.1,.25),(.55,.35,.25),'.5 .31 .17 1'),
              container('bin',4.8,1.4,.05,.40,.40,.35,'.27 .35 .78 1'),
              box('throw_pedestal',(3,1.4,.44),(.19,.19,.44),'.6 .6 .65 1')]
    # Kitchen: counter with three mats, sink, refrigerator, two facing drawers.
    props += [box('counter',(11.2,2.5,.40),(.65,1.9,.40),'.8 .8 .76 1'),
              box('counter_top',(11.15,2.5,.84),(.73,1.98,.04),'.36 .36 .36 1'),
              box('fridge',(7.5,4.5,1),(.55,.4,1),'.85 .89 .9 1'),
              box('fridge_divider',(7.5,4.08,1.45),(.55,.025,.02),'.2 .2 .2 1'),
              box('sink_dark',(11.10,3.95,.886),(.38,.32,.009),'.1 .18 .19 1'),
              '<geom name="faucet" type="capsule" fromto="11.4 3.95 .9 11.4 3.95 1.17" size=".03" rgba=".8 .8 .8 1"/>']
    for i,y in enumerate((1.0,2.0,3.0)):
        props.append(box('mat'+str(i),(10.80,y,.888),(.25,.30,.008),['.85 .4 .2 1','.25 .7 .65 1','.6 .35 .75 1'][i]))
    for i,(cx,cy) in enumerate(DRAWER_CENTERS):
        label = 'AB'[i]
        # A single side-by-side bank faces the open kitchen floor. This removes
        # the old narrow through-gap and leaves the counter approach unobstructed.
        props.append(f'<body name="drawer_station_{label}" pos="{cx} {cy} 0" euler="0 0 1.5707963267948966">')
        props += [box('cabinet'+label+'_side1',(0,-.45,.49),(.46,.035,.49),'.47 .34 .25 1'),
                  box('cabinet'+label+'_side2',(0,.45,.49),(.46,.035,.49),'.47 .34 .25 1'),
                  box('cabinet'+label+'_back',(.45,0,.49),(.035,.45,.49),'.47 .34 .25 1'),
                  box('cabinet'+label+'_top',(0,0,1.02),(.49,.49,.035),'.47 .34 .25 1')]
        props.append(f'<body name="drawer{label}" pos="0 0 .60"><joint name="drawer{label}" type="slide" axis="-1 0 0" range="0 .5" damping="8" frictionloss="3"/>' +
                     container('drawer'+label,0,0,0,.40,.38,.17,'.58 .43 .3 1') +
                     box('drawer'+label+'_front',(-.43,0,.16),(.04,.40,.22),'.7 .5 .32 1') +
                     f'<geom name="handle{label}" type="capsule" fromto="-.62 -.16 .18 -.62 .16 .18" size=".025" rgba=".15 .15 .17 1"/>' +
                     f'<geom type="capsule" fromto="-.62 -.16 .18 -.43 -.16 .18" size=".018" rgba=".15 .15 .17 1"/><geom type="capsule" fromto="-.62 .16 .18 -.43 .16 .18" size=".018" rgba=".15 .15 .17 1"/>' +
                     (box('latchB',(-.50,.26,.31),(.04,.065,.04),'.9 .22 .05 1') if i else '') + '</body>')
        # A and B are ordinary visible markings, constructed with dark strokes.
        if label == 'A':
            lines = [((-.48,-.07,.91),(-.48,0,.99)),((-.48,0,.99),(-.48,.07,.91)),((-.48,-.035,.95),(-.48,.035,.95))]
        else:
            lines = [((-.48,-.04,.91),(-.48,-.04,.99)),((-.48,-.04,.99),(-.48,.04,.97)),((-.48,.04,.97),(-.48,-.04,.95)),((-.48,-.04,.95),(-.48,.04,.93)),((-.48,.04,.93),(-.48,-.04,.91))]
        for j,(a,b) in enumerate(lines):
            props.append(f'<geom name="label{label}{j}" type="capsule" fromto="{" ".join(map(str,a+b))}" size=".008" rgba=".08 .08 .08 1" contype="0" conaffinity="0"/>')
        props.append('</body>')
    # Bathroom cues, all fixed and nonfunctional.
    props += [box('bath',(10.7,8.9,.32),(.6,.85,.32),'.9 .94 .95 1'),
              box('bath_water',(10.7,8.9,.66),(.49,.74,.025),'.3 .6 .72 1'),
              '<geom name="toilet" type="ellipsoid" pos="8 8 .37" size=".28 .38 .37" rgba=".95 .95 .95 1"/>',
              box('toilet_tank',(8,8.45,.65),(.28,.15,.40),'.94 .94 .94 1'),
              box('bath_sink',(7.1,6.6,.75),(.5,.35,.1),'.9 .94 .95 1')]
    for i,(x,y) in enumerate(CHARGERS):
        props += [box('charger'+str(i),(x,y,.002),(.40,.40,.002),'.10 .7 .35 1'),
                  box('charger_back'+str(i),(x-.36,y,.22),(.06,.40,.22),'.18 .25 .22 1'),
                  box('charge_mark'+str(i),(x,y,.005),(.04,.2,.001),'.94 .95 .3 1')]
        if i==1:
            # Deliberately inaccessible bedroom port, perceptible only through
            # ordinary sensors. Existing west backing plus three fixed rails
            # encloses the pad; the planar mobile base cannot enter or climb it.
            props += [box('bedroom_charger_east_guard',(x+.36,y,.22),(.06,.40,.22),'.18 .25 .22 1'),
                      box('bedroom_charger_north_guard',(x,y+.36,.22),(.40,.06,.22),'.18 .25 .22 1'),
                      box('bedroom_charger_south_guard',(x,y-.36,.22),(.40,.06,.22),'.18 .25 .22 1')]
    objects=[]
    for i,(name,size,color) in enumerate(TOYS):
        objects.append(f'<body name="{name}" pos="{2.5+i*.6} 6.2 {size[2]+.02}"><freejoint name="{name}_free"/>'+box(name+'_geom',(0,0,0),size,color,mass=.10+i*.03)+'</body>')
    objects += ['<body name="cup" pos="10.8 2 .93"><freejoint name="cup_free"/><geom name="cup_geom" type="cylinder" size=".032 .045" mass=".10" condim="6" rgba=".95 .9 .82 1"/><geom type="cylinder" pos="0 0 .045" size=".025 .001" rgba=".22 .16 .12 1" contype="0" conaffinity="0" mass=".001"/></body>',
                '<body name="ball" pos="3 1.4 .94"><freejoint name="ball_free"/><geom name="ball_geom" type="sphere" size=".045" mass=".06" condim="6" friction="1 .02 .01" rgba=".95 .35 .12 1"/></body>']
    robot='''<body name="base" pos="3 2 .21" childclass="robot">
      <joint name="base_x" type="slide" axis="1 0 0"/><joint name="base_y" type="slide" axis="0 1 0"/><joint name="base_yaw" type="hinge" axis="0 0 1"/>
      <geom name="base_shell" type="box" size=".28 .24 .16" mass="35" rgba=".22 .28 .35 1"/>
      <geom type="cylinder" pos="0 .26 -.1" euler="1.5708 0 0" size=".1 .025" contype="0" conaffinity="0" rgba=".06 .06 .06 1"/>
      <geom type="cylinder" pos="0 -.26 -.1" euler="1.5708 0 0" size=".1 .025" contype="0" conaffinity="0" rgba=".06 .06 .06 1"/>
      <geom type="box" pos="-.15 0 .57" size=".07 .07 .5" rgba=".55 .6 .64 1"/>
      <body name="head" pos="-.13 0 1.07"><inertial pos="0 0 0" mass=".1" diaginertia=".001 .001 .001"/><joint name="head_pan" axis="0 0 1" range="-3.14 3.14" damping="2"/>
       <body name="head_tilt_body"><joint name="head_tilt" axis="0 1 0" range="-1.2 1.2" damping="2"/>
        <geom type="box" size=".08 .12 .06" mass=".2" rgba=".12 .15 .17 1" contype="0" conaffinity="0"/>
        <camera name="head_rgbd" pos=".10 0 0" xyaxes="0 -1 0 0 0 1" fovy="72"/>
       </body></body>
      <body name="arm_lift" pos=".08 0 .22"><joint name="lift" type="slide" axis="0 0 1" range="-.41 .92" damping="30"/>
       <geom type="box" size=".12 .09 .06" mass="2" rgba=".7 .73 .76 1"/>
       <body name="arm_reach"><joint name="reach" type="slide" axis="1 0 0" range=".12 .95" damping="20"/>
        <geom type="box" pos="-.12 0 .15" size=".15 .05 .04" mass="1" rgba=".65 .69 .74 1"/>
        <body name="arm_lateral"><joint name="lateral" type="slide" axis="0 1 0" range="-.45 .45" damping="15"/>
         <geom type="box" pos="0 0 .15" size=".055 .05 .05" mass=".3" rgba=".6 .67 .7 1"/>
         <body name="wrist"><joint name="wrist_pitch" axis="0 1 0" range="-1.4 1.4" damping="1"/>
          <geom name="palm" type="box" pos="0 0 .055" size=".035 .095 .025" mass=".3" rgba=".2 .24 .28 1"/>
          <site name="tcp" pos="0 0 0" size=".005"/>
          <camera name="wrist_rgb" pos=".035 0 .13" xyaxes="0 -1 0 1 0 0" fovy="80"/>
          <body name="finger_left" pos="0 .009 0"><joint name="finger_left" type="slide" axis="0 1 0" range="0 .075" damping="1"/>
           <geom name="finger_left_geom" type="box" size=".04 .009 .05" mass=".08" rgba=".13 .15 .17 1" friction="2.5 .05 .01"/></body>
          <body name="finger_right" pos="0 -.009 0"><joint name="finger_right" type="slide" axis="0 -1 0" range="0 .075" damping="1"/>
           <geom name="finger_right_geom" type="box" size=".04 .009 .05" mass=".08" rgba=".13 .15 .17 1" friction="2.5 .05 .01"/></body>
         </body></body></body></body></body>'''
    actuators=[]
    for joint,kp,force in [('base_x',2500,2000),('base_y',2500,2000),('base_yaw',1500,1000),('head_pan',150,50),('head_tilt',150,50),
                           ('lift',2500,900),('reach',2500,900),('lateral',2500,900),('wrist_pitch',250,80),('finger_left',300,35),('finger_right',300,35)]:
        damping={'base_x':600,'base_y':600,'base_yaw':150,'lift':180,'reach':120,'lateral':80,'head_pan':12,'head_tilt':12,'wrist_pitch':20,'finger_left':8,'finger_right':8}[joint]
        actuators.append(f'<position name="{joint}" joint="{joint}" kp="{kp}" kv="{damping}" forcerange="-{force} {force}"/>')
    robot=robot.replace('<body name="arm_', '<body gravcomp="1" name="arm_').replace('<body name="wrist"','<body gravcomp="1" name="wrist"').replace('<body name="finger_', '<body gravcomp="1" name="finger_')
    return '<mujoco model="apartment-cartesian-mobile-v1"><compiler angle="radian" autolimits="true"/><option timestep=".004" integrator="implicitfast" cone="elliptic" iterations="60" ccd_tolerance="1e-10"/><size nconmax="300" njmax="2000"/><visual><global offwidth="960" offheight="720"/><quality shadowsize="2048"/></visual><default><geom friction="1 .02 .002" solref=".01 1" solimp=".95 .99 .001" conaffinity="3"/><joint armature=".01"/><default class="robot"><geom contype="2" conaffinity="1"/></default></default><worldbody><light pos="3 3 7" diffuse=".85 .85 .85"/><light pos="9 8 7" diffuse=".75 .75 .75"/>' + ''.join(props+objects)+robot+'</worldbody><actuator>'+''.join(actuators)+'</actuator></mujoco>'
