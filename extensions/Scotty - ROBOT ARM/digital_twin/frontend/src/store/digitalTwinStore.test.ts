import { beforeEach, describe, expect, it } from "vitest";
import { selectors, useDigitalTwinStore } from "./digitalTwinStore";
import type { ModelInfo, RobotStatus } from "../lib/types";

const baseStatus: RobotStatus = {
  connected: true,
  live_enabled: true,
  movement_enabled: true,
  homed: true,
  estop: false,
  error: null,
  moving: false,
  simulator_active: false,
  hardware_connected: true,
  angles_deg: [0, 0, 0, 0, 0, 0],
  target_angles_deg: null,
  pose: null,
  tcp_pose_m_rad: null,
  speeds: null,
  io: null,
  activity: null,
  message: ""
};

const model: ModelInfo = {
  urdf_url: "/model.urdf",
  package_name: "parol6",
  package_url: "/assets/",
  mesh_url: "/assets/meshes/",
  joint_limits: [
    { name: "L1", lower_deg: -180, upper_deg: 180 },
    { name: "L2", lower_deg: -180, upper_deg: 180 },
    { name: "L3", lower_deg: -180, upper_deg: 300 },
    { name: "L4", lower_deg: -180, upper_deg: 180 },
    { name: "L5", lower_deg: -180, upper_deg: 180 },
    { name: "L6", lower_deg: -180, upper_deg: 360 }
  ],
  home_angles_deg: [0, 0, 0, 0, 0, 0],
  named_states: []
};

describe("digital twin live movement selector", () => {
  it("requires all live safety gates", () => {
    expect(selectors.canSendLiveMove(baseStatus)).toBe(true);
    expect(selectors.canSendLiveMove({ ...baseStatus, live_enabled: false })).toBe(false);
    expect(selectors.canSendLiveMove({ ...baseStatus, movement_enabled: false })).toBe(false);
    expect(selectors.canSendLiveMove({ ...baseStatus, homed: false })).toBe(false);
    expect(selectors.canSendLiveMove({ ...baseStatus, estop: true })).toBe(false);
    expect(selectors.canSendLiveMove({ ...baseStatus, error: "fault" })).toBe(false);
  });
});

describe("movement programming store", () => {
  beforeEach(() => {
    window.localStorage.clear();
    useDigitalTwinStore.setState({
      model,
      status: { ...baseStatus, live_enabled: false },
      previewAngles: [1, 2, 3, 4, 5, 6],
      anchorPose: [0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
      savedPositions: [],
      movementOrders: [],
      movementGraphs: [],
      selectedOrderId: null,
      selectedGraphId: null,
      executionState: { mode: "idle", message: "Ready", errors: [] },
      log: []
    });
  });

  it("saves, loads, updates, removes, and exports robot poses", () => {
    const store = useDigitalTwinStore.getState();
    store.saveCurrentPosition("Pick pose", "Above red brick");

    let next = useDigitalTwinStore.getState();
    expect(next.savedPositions).toHaveLength(1);
    expect(next.savedPositions[0].name).toBe("Pick pose");
    expect(next.savedPositions[0].description).toBe("Above red brick");
    expect(next.savedPositions[0].jointValues).toEqual([1, 2, 3, 4, 5, 6]);
    expect(selectors.cartesianPoseToArray(next.savedPositions[0].cartesianPose)).toEqual([0.1, 0.2, 0.3, 0.4, 0.5, 0.6]);

    useDigitalTwinStore.setState({
      previewAngles: [0, 0, 0, 0, 0, 0],
      anchorPose: [0, 0, 0, 0, 0, 0]
    });
    next.loadSavedPosition(next.savedPositions[0].id);
    expect(useDigitalTwinStore.getState().previewAngles).toEqual([1, 2, 3, 4, 5, 6]);
    expect(useDigitalTwinStore.getState().anchorPose).toEqual([0.1, 0.2, 0.3, 0.4, 0.5, 0.6]);

    useDigitalTwinStore.setState({ previewAngles: [6, 5, 4, 3, 2, 1] });
    useDigitalTwinStore.getState().replaceSavedPositionWithCurrentPose(next.savedPositions[0].id);
    expect(useDigitalTwinStore.getState().savedPositions[0].jointValues).toEqual([6, 5, 4, 3, 2, 1]);

    const exported = JSON.parse(useDigitalTwinStore.getState().exportSavedPositions());
    expect(exported.format).toBe("parol6-digital-twin-positions/v2");
    expect(exported.positions[0].name).toBe("Pick pose");

    useDigitalTwinStore.getState().deleteSavedPosition(next.savedPositions[0].id);
    expect(useDigitalTwinStore.getState().savedPositions).toHaveLength(0);
  });

  it("creates movement orders from saved positions and reorders steps", () => {
    const store = useDigitalTwinStore.getState();
    store.saveCurrentPosition("A");
    useDigitalTwinStore.setState({ previewAngles: [10, 11, 12, 13, 14, 15] });
    useDigitalTwinStore.getState().saveCurrentPosition("B");
    const positions = useDigitalTwinStore.getState().savedPositions;

    const orderId = useDigitalTwinStore.getState().createMovementOrder("Pick and place");
    useDigitalTwinStore.getState().addPositionToOrder(orderId, positions[0].id);
    useDigitalTwinStore.getState().addPositionToOrder(orderId, positions[1].id);

    let order = useDigitalTwinStore.getState().movementOrders[0];
    expect(order.steps.map((step) => step.positionId)).toEqual([positions[0].id, positions[1].id]);
    expect(useDigitalTwinStore.getState().validateMovementOrder(orderId).valid).toBe(true);

    useDigitalTwinStore.getState().reorderOrderStep(orderId, order.steps[1].id, 0);
    order = useDigitalTwinStore.getState().movementOrders[0];
    expect(order.steps.map((step) => step.positionId)).toEqual([positions[1].id, positions[0].id]);
  });

  it("validates a conditional movement graph with camera color branching", () => {
    const store = useDigitalTwinStore.getState();
    store.saveCurrentPosition("Red bin");
    const positionId = useDigitalTwinStore.getState().savedPositions[0].id;
    const graphId = useDigitalTwinStore.getState().createMovementGraph("Color sort");
    const state = useDigitalTwinStore.getState();
    const graph = state.movementGraphs[0];
    const start = graph.startNodeId;
    const camera = state.addGraphNode(graphId, "camera")!;
    const picker = useDigitalTwinStore.getState().addGraphNode(graphId, "colorPicker")!;
    const condition = useDigitalTwinStore.getState().addGraphNode(graphId, "conditional")!;
    const redPosition = useDigitalTwinStore.getState().addGraphNode(graphId, "position")!;

    useDigitalTwinStore.getState().updateGraphNode(graphId, picker, { sourceNodeId: camera });
    useDigitalTwinStore.getState().updateGraphNode(graphId, redPosition, { positionId });
    useDigitalTwinStore.getState().connectGraphNodes(graphId, start, camera);
    useDigitalTwinStore.getState().connectGraphNodes(graphId, camera, picker);
    useDigitalTwinStore.getState().connectGraphNodes(graphId, picker, condition);
    useDigitalTwinStore.getState().connectGraphNodes(graphId, condition, redPosition, "red");
    useDigitalTwinStore.getState().connectGraphNodes(graphId, condition, redPosition, "blue");
    useDigitalTwinStore.getState().connectGraphNodes(graphId, condition, redPosition, "unknown");

    expect(useDigitalTwinStore.getState().validateMovementGraph(graphId).valid).toBe(true);
  });
});
