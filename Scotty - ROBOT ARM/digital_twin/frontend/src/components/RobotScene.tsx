import { OrbitControls, Grid, Html, TransformControls } from "@react-three/drei";
import { Canvas, ThreeEvent, useFrame } from "@react-three/fiber";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Group, LoadingManager, Object3D, Quaternion, Vector3 } from "three";
import URDFLoader from "urdf-loader";
import { selectors, useDigitalTwinStore } from "../store/digitalTwinStore";

type UrdfJoint = {
  setJointValue?: (value: number) => void;
};

type UrdfRobot = Object3D & {
  joints?: Record<string, UrdfJoint>;
};

type JointRigPose = {
  position: [number, number, number];
  quaternion: [number, number, number, number];
};

type WristRigPoses = Partial<Record<"L5" | "L6", JointRigPose>>;
type FramePoseMap = Partial<Record<string, JointRigPose>>;

const FRAME_NAMES = ["world", "base_link", "L1", "L2", "L3", "L4", "L5", "L6", "gripper", "tcp"];
const ZERO = new Vector3(0, 0, 0);

function modelToScenePosition(pose: number[]): [number, number, number] {
  return [pose[0] ?? 0, pose[2] ?? 0, -(pose[1] ?? 0)];
}

function modelToSceneRotation(pose: number[]): [number, number, number] {
  return [pose[3] ?? 0, pose[4] ?? 0, pose[5] ?? 0];
}

function sceneToModelPose(object: Object3D, previousPose: number[]): number[] {
  const position = object.position;
  const rx = Number.isFinite(object.rotation.x) ? object.rotation.x : previousPose[3] ?? 0;
  const ry = Number.isFinite(object.rotation.y) ? object.rotation.y : previousPose[4] ?? 0;
  const rz = Number.isFinite(object.rotation.z) ? object.rotation.z : previousPose[5] ?? 0;
  return [
    position.x,
    -position.z,
    position.y,
    rx,
    ry,
    rz
  ];
}

function resolveJointName(object: Object3D): string | null {
  let current: Object3D | null = object;
  while (current) {
    const match = current.name.match(/^L[1-6]$/);
    if (match) return match[0];
    current = current.parent;
  }
  return null;
}

function jointPoseChanged(current: JointRigPose | undefined, next: JointRigPose): boolean {
  if (!current) return true;
  const dp = Math.hypot(
    current.position[0] - next.position[0],
    current.position[1] - next.position[1],
    current.position[2] - next.position[2]
  );
  const dot = Math.abs(
    current.quaternion[0] * next.quaternion[0] +
    current.quaternion[1] * next.quaternion[1] +
    current.quaternion[2] * next.quaternion[2] +
    current.quaternion[3] * next.quaternion[3]
  );
  return dp > 0.001 || dot < 0.9999;
}

function framePosesChanged(current: FramePoseMap, next: FramePoseMap): boolean {
  const keys = new Set([...Object.keys(current), ...Object.keys(next)]);
  for (const key of keys) {
    const nextPose = next[key];
    if (!nextPose) return true;
    if (jointPoseChanged(current[key], nextPose)) return true;
  }
  return false;
}

function RobotModel({
  onTcpScenePosition,
  onWristRigPoses,
  onFramePoses
}: {
  onTcpScenePosition: (position: Vector3) => void;
  onWristRigPoses: (poses: WristRigPoses) => void;
  onFramePoses: (poses: FramePoseMap) => void;
}) {
  const model = useDigitalTwinStore((state) => state.model);
  const previewAngles = useDigitalTwinStore((state) => state.previewAngles);
  const selectedJoint = useDigitalTwinStore((state) => state.selectedJoint);
  const setSelectedJoint = useDigitalTwinStore((state) => state.setSelectedJoint);
  const [robot, setRobot] = useState<UrdfRobot | null>(null);
  const robotRef = useRef<UrdfRobot | null>(null);
  const rigPosesRef = useRef<WristRigPoses>({});
  const framePosesRef = useRef<FramePoseMap>({});

  useEffect(() => {
    if (!model) return;
    const manager = new LoadingManager();
    const loader = new URDFLoader(manager);
    loader.packages = {
      [model.package_name]: model.package_url
    };
    loader.load(
      model.urdf_url,
      (loaded) => {
        const urdfRobot = loaded as UrdfRobot;
        urdfRobot.traverse((child) => {
          child.castShadow = true;
          child.receiveShadow = true;
          const maybeMesh = child as Object3D & {
            isMesh?: boolean;
            material?: { transparent?: boolean; opacity?: number; depthWrite?: boolean; roughness?: number; metalness?: number } | Array<{ transparent?: boolean; opacity?: number; depthWrite?: boolean; roughness?: number; metalness?: number }>;
          };
          if (maybeMesh.isMesh && maybeMesh.material) {
            const materials = Array.isArray(maybeMesh.material) ? maybeMesh.material : [maybeMesh.material];
            materials.forEach((material) => {
              material.transparent = false;
              material.opacity = 1;
              material.depthWrite = true;
              if ("roughness" in material) material.roughness = 0.68;
              if ("metalness" in material) material.metalness = 0.05;
            });
          }
        });
        robotRef.current = urdfRobot;
        setRobot(urdfRobot);
      },
      undefined,
      (err) => {
        console.error("URDF load failed", err);
      }
    );
  }, [model]);

  useFrame(() => {
    const active = robotRef.current;
    if (!active?.joints) return;
    previewAngles.forEach((angle, index) => {
      const joint = active.joints?.[`L${index + 1}`];
      joint?.setJointValue?.((angle * Math.PI) / 180);
    });
    active.updateMatrixWorld(true);
    const tcpObject = active.getObjectByName("tcp") ?? (active.joints.L6 as unknown as Object3D | undefined);
    if (tcpObject) {
      const tcpPosition = new Vector3();
      tcpObject.getWorldPosition(tcpPosition);
      onTcpScenePosition(tcpPosition);
    }
    const framePoses: FramePoseMap = {};
    for (const name of FRAME_NAMES) {
      const frame = active.getObjectByName(name);
      if (!frame) continue;
      const position = new Vector3();
      const quaternion = new Quaternion();
      frame.getWorldPosition(position);
      frame.getWorldQuaternion(quaternion);
      framePoses[name] = {
        position: position.toArray() as [number, number, number],
        quaternion: quaternion.toArray() as [number, number, number, number]
      };
    }
    if (framePosesChanged(framePosesRef.current, framePoses)) {
      framePosesRef.current = framePoses;
      onFramePoses(framePoses);
    }
    const nextRigPoses: WristRigPoses = {};
    for (const name of ["L5", "L6"] as const) {
      const joint = active.joints[name] as unknown as Object3D | undefined;
      if (!joint) continue;
      const position = new Vector3();
      const quaternion = new Quaternion();
      joint.getWorldPosition(position);
      joint.getWorldQuaternion(quaternion);
      nextRigPoses[name] = {
        position: position.toArray() as [number, number, number],
        quaternion: quaternion.toArray() as [number, number, number, number]
      };
    }
    if (
      (nextRigPoses.L5 && jointPoseChanged(rigPosesRef.current.L5, nextRigPoses.L5)) ||
      (nextRigPoses.L6 && jointPoseChanged(rigPosesRef.current.L6, nextRigPoses.L6))
    ) {
      rigPosesRef.current = nextRigPoses;
      onWristRigPoses(nextRigPoses);
    }
  });

  const jointLabel = useMemo(() => selectedJoint ?? "click a link", [selectedJoint]);

  if (!model) {
    return <Html center>Loading model metadata...</Html>;
  }

  if (!robot) {
    return <Html center>Loading PAROL6 URDF...</Html>;
  }

  const onPointerDown = (event: ThreeEvent<PointerEvent>) => {
    event.stopPropagation();
    setSelectedJoint(resolveJointName(event.object));
  };

  return (
    <group rotation={[-Math.PI / 2, 0, 0]} onPointerDown={onPointerDown}>
      <primitive object={robot} />
      <Html position={[0.18, 0.22, 0]} className="sceneHint">
        {jointLabel}
      </Html>
    </group>
  );
}

function FrameAxes({ name, pose, size = 0.055 }: { name: string; pose: JointRigPose; size?: number }) {
  const axes = useMemo(
    () => [
      { direction: new Vector3(1, 0, 0), color: "#ef4b4b", label: "X" },
      { direction: new Vector3(0, 1, 0), color: "#42c875", label: "Y" },
      { direction: new Vector3(0, 0, 1), color: "#4c8dff", label: "Z" }
    ],
    []
  );
  return (
    <group position={pose.position} quaternion={pose.quaternion}>
      {axes.map((axis) => (
        <group key={axis.label}>
          <arrowHelper args={[axis.direction, ZERO, size, axis.color, size * 0.26, size * 0.11]} />
          <Html position={axis.direction.clone().multiplyScalar(size * 1.14).toArray()} className="axisLabel">
            {axis.label}
          </Html>
        </group>
      ))}
      <Html position={[size * 0.18, size * 0.18, size * 0.18]} className="frameLabel">
        {name}
      </Html>
    </group>
  );
}

function WristJointRig({
  name,
  index,
  pose,
  onDragStateChange
}: {
  name: "L5" | "L6";
  index: number;
  pose: JointRigPose;
  onDragStateChange: (dragging: boolean) => void;
}) {
  const angle = useDigitalTwinStore((state) => state.previewAngles[index] ?? 0);
  const selectedJoint = useDigitalTwinStore((state) => state.selectedJoint);
  const setJointPreview = useDigitalTwinStore((state) => state.setJointPreview);
  const setSelectedJoint = useDigitalTwinStore((state) => state.setSelectedJoint);
  const dragRef = useRef<{ startX: number; startY: number; startAngle: number } | null>(null);
  const selected = selectedJoint === name;

  const onPointerDown = (event: ThreeEvent<PointerEvent>) => {
    event.stopPropagation();
    setSelectedJoint(name);
    onDragStateChange(true);
    dragRef.current = {
      startX: event.nativeEvent.clientX,
      startY: event.nativeEvent.clientY,
      startAngle: angle
    };
    if (event.nativeEvent.target instanceof Element) {
      event.nativeEvent.target.setPointerCapture(event.pointerId);
    }
  };

  const onPointerMove = (event: ThreeEvent<PointerEvent>) => {
    if (!dragRef.current) return;
    event.stopPropagation();
    const dx = event.nativeEvent.clientX - dragRef.current.startX;
    const dy = event.nativeEvent.clientY - dragRef.current.startY;
    setJointPreview(index, dragRef.current.startAngle + (dx - dy) * 0.35);
  };

  const onPointerUp = (event: ThreeEvent<PointerEvent>) => {
    if (!dragRef.current) return;
    event.stopPropagation();
    dragRef.current = null;
    onDragStateChange(false);
    if (event.nativeEvent.target instanceof Element && event.nativeEvent.target.hasPointerCapture(event.pointerId)) {
      event.nativeEvent.target.releasePointerCapture(event.pointerId);
    }
  };

  return (
    <group position={pose.position} quaternion={pose.quaternion}>
      <mesh
        renderOrder={10}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        <torusGeometry args={[name === "L5" ? 0.052 : 0.043, selected ? 0.005 : 0.003, 12, 64]} />
        <meshStandardMaterial
          color={selected ? "#ffb454" : "#5fd0ff"}
          emissive={selected ? "#8a4a00" : "#003f5a"}
          emissiveIntensity={0.55}
          transparent
          opacity={0.9}
          depthTest={false}
        />
      </mesh>
      <mesh
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        <torusGeometry args={[name === "L5" ? 0.052 : 0.043, 0.011, 8, 40]} />
        <meshBasicMaterial transparent opacity={0} depthWrite={false} />
      </mesh>
      <Html position={[0.045, 0.02, 0]} className="sceneHint">
        {name} {angle.toFixed(1)} deg
      </Html>
    </group>
  );
}

function CartesianAnchor({ onDragStateChange }: { onDragStateChange: (dragging: boolean) => void }) {
  const anchorRef = useRef<Group | null>(null);
  const [anchorObject, setAnchorObject] = useState<Group | null>(null);
  const anchorPose = useDigitalTwinStore((state) => state.anchorPose);
  const anchorTransformMode = useDigitalTwinStore((state) => state.anchorTransformMode);
  const status = useDigitalTwinStore((state) => state.status);
  const applyAnchorOnRelease = useDigitalTwinStore((state) => state.applyAnchorOnRelease);
  const setAnchorPose = useDigitalTwinStore((state) => state.setAnchorPose);
  const solveAnchorTarget = useDigitalTwinStore((state) => state.solveAnchorTarget);
  const moveToAnchor = useDigitalTwinStore((state) => state.moveToAnchor);
  const canLiveMove = selectors.canSendLiveMove(status);

  useEffect(() => {
    if (!anchorRef.current) return;
    anchorRef.current.position.fromArray(modelToScenePosition(anchorPose));
    anchorRef.current.rotation.fromArray(modelToSceneRotation(anchorPose));
  }, [anchorPose]);

  const commitAnchor = async () => {
    if (!anchorRef.current) return;
    const nextPose = sceneToModelPose(anchorRef.current, anchorPose);
    setAnchorPose(nextPose);
    await solveAnchorTarget(nextPose);
    if (applyAnchorOnRelease && canLiveMove) {
      await moveToAnchor(nextPose);
    }
  };

  const previewAnchor = () => {
    if (!anchorRef.current) return;
    setAnchorPose(sceneToModelPose(anchorRef.current, anchorPose));
  };

  return (
    <>
      <group
        ref={(node) => {
          anchorRef.current = node;
          if (node && anchorObject !== node) setAnchorObject(node);
        }}
        position={modelToScenePosition(anchorPose)}
        rotation={modelToSceneRotation(anchorPose)}
      >
        <mesh castShadow>
          <sphereGeometry args={[0.015, 24, 24]} />
          <meshStandardMaterial color="#f2d27b" emissive="#80622b" emissiveIntensity={0.25} />
        </mesh>
        <mesh rotation={[0, 0, Math.PI / 2]}>
          <torusGeometry args={[0.028, 0.0025, 8, 32]} />
          <meshStandardMaterial color="#f2d27b" />
        </mesh>
        <Html position={[0.025, 0.025, 0]} className="sceneHint">
          TCP target
        </Html>
      </group>
      {anchorObject ? (
        <TransformControls
          object={anchorObject}
          mode={anchorTransformMode}
          space={anchorTransformMode === "rotate" ? "local" : "world"}
          size={0.75}
          onMouseDown={() => onDragStateChange(true)}
          onObjectChange={previewAnchor}
          onMouseUp={() => {
            onDragStateChange(false);
            void commitAnchor();
          }}
        />
      ) : null}
    </>
  );
}

export function RobotScene() {
  const selectedJoint = useDigitalTwinStore((state) => state.selectedJoint);
  const setJointPreview = useDigitalTwinStore((state) => state.setJointPreview);
  const previewAngles = useDigitalTwinStore((state) => state.previewAngles);
  const anchorPose = useDigitalTwinStore((state) => state.anchorPose);
  const setAnchorPose = useDigitalTwinStore((state) => state.setAnchorPose);
  const [anchorDragging, setAnchorDragging] = useState(false);
  const [jointRigDragging, setJointRigDragging] = useState(false);
  const [wristRigPoses, setWristRigPoses] = useState<WristRigPoses>({});
  const [framePoses, setFramePoses] = useState<FramePoseMap>({});

  const syncAnchorToRenderedTcp = (scenePosition: Vector3) => {
    if (anchorDragging) return;
    const dummy = new Object3D();
    dummy.position.copy(scenePosition);
    dummy.rotation.fromArray(modelToSceneRotation(anchorPose));
    const nextPose = sceneToModelPose(dummy, anchorPose);
    const dx = nextPose[0] - anchorPose[0];
    const dy = nextPose[1] - anchorPose[1];
    const dz = nextPose[2] - anchorPose[2];
    if (Math.hypot(dx, dy, dz) > 0.002) {
      setAnchorPose(nextPose);
    }
  };

  const onWheel = (event: React.WheelEvent<HTMLDivElement>) => {
    if (!selectedJoint) return;
    event.preventDefault();
    const index = Number(selectedJoint.slice(1)) - 1;
    const direction = event.deltaY > 0 ? -1 : 1;
    setJointPreview(index, previewAngles[index] + direction);
  };

  return (
    <div className="sceneFrame" onWheel={onWheel}>
      <Canvas shadows camera={{ position: [0.62, 0.42, 0.78], fov: 42 }} gl={{ antialias: true }}>
        <color attach="background" args={["#11161b"]} />
        <hemisphereLight args={["#eef5ff", "#2d352f", 1.25]} />
        <ambientLight intensity={0.32} />
        <directionalLight
          position={[0.9, 1.15, 0.55]}
          intensity={2.4}
          castShadow
          shadow-mapSize={[2048, 2048]}
          shadow-camera-near={0.1}
          shadow-camera-far={4}
          shadow-camera-left={-1.2}
          shadow-camera-right={1.2}
          shadow-camera-top={1.2}
          shadow-camera-bottom={-1.2}
        />
        <directionalLight position={[-0.55, 0.55, -0.85]} intensity={0.85} />
        <Suspense fallback={<Html center>Loading...</Html>}>
          <RobotModel
            onTcpScenePosition={syncAnchorToRenderedTcp}
            onWristRigPoses={setWristRigPoses}
            onFramePoses={setFramePoses}
          />
          {Object.entries(framePoses).map(([name, pose]) =>
            pose ? (
              <FrameAxes key={name} name={name} pose={pose} size={name === "tcp" ? 0.075 : name === "world" ? 0.09 : 0.045} />
            ) : null
          )}
          {wristRigPoses.L5 ? (
            <WristJointRig name="L5" index={4} pose={wristRigPoses.L5} onDragStateChange={setJointRigDragging} />
          ) : null}
          {wristRigPoses.L6 ? (
            <WristJointRig name="L6" index={5} pose={wristRigPoses.L6} onDragStateChange={setJointRigDragging} />
          ) : null}
          <CartesianAnchor onDragStateChange={setAnchorDragging} />
        </Suspense>
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.004, 0]} receiveShadow>
          <planeGeometry args={[1.3, 1.3]} />
          <meshStandardMaterial color="#20262b" roughness={0.82} metalness={0} />
        </mesh>
        <Grid args={[1.2, 24]} cellSize={0.05} sectionSize={0.25} position={[0, -0.002, 0]} />
        <OrbitControls makeDefault enableDamping enabled={!anchorDragging && !jointRigDragging} target={[0.02, 0.18, -0.08]} />
      </Canvas>
    </div>
  );
}
