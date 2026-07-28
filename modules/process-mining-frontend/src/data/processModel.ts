export const productionProcessBpmn = `<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" xmlns:di="http://www.omg.org/spec/DD/20100524/DI" id="Definitions_TinyHouse" targetNamespace="http://tinyhouse.local/process-mining">
  <bpmn:process id="Process_Production" name="TinyHouse Assisted Production" isExecutable="false">
    <bpmn:startEvent id="StartEvent_Order" name="Part order received">
      <bpmn:outgoing>Flow_Start_Print</bpmn:outgoing>
    </bpmn:startEvent>
    <bpmn:task id="Task_Print" name="Print part">
      <bpmn:incoming>Flow_Start_Print</bpmn:incoming><bpmn:outgoing>Flow_Print_Remove</bpmn:outgoing>
    </bpmn:task>
    <bpmn:manualTask id="Task_Remove" name="Remove from print bed">
      <bpmn:incoming>Flow_Print_Remove</bpmn:incoming><bpmn:outgoing>Flow_Remove_Pick</bpmn:outgoing>
    </bpmn:manualTask>
    <bpmn:serviceTask id="Task_Pick" name="Robot picks part">
      <bpmn:incoming>Flow_Remove_Pick</bpmn:incoming><bpmn:outgoing>Flow_Pick_Color</bpmn:outgoing>
    </bpmn:serviceTask>
    <bpmn:task id="Task_Color" name="Check color">
      <bpmn:incoming>Flow_Pick_Color</bpmn:incoming><bpmn:incoming>Flow_Recheck_Color</bpmn:incoming><bpmn:outgoing>Flow_Color_Gateway</bpmn:outgoing>
    </bpmn:task>
    <bpmn:exclusiveGateway id="Gateway_Color" name="Color accepted?" default="Flow_Color_Recheck">
      <bpmn:incoming>Flow_Color_Gateway</bpmn:incoming><bpmn:outgoing>Flow_Color_Store</bpmn:outgoing><bpmn:outgoing>Flow_Color_Recheck</bpmn:outgoing>
    </bpmn:exclusiveGateway>
    <bpmn:task id="Task_Recheck" name="Calibrate &amp; recheck">
      <bpmn:incoming>Flow_Color_Recheck</bpmn:incoming><bpmn:outgoing>Flow_Recheck_Color</bpmn:outgoing>
    </bpmn:task>
    <bpmn:serviceTask id="Task_Store" name="Store in drawer">
      <bpmn:incoming>Flow_Color_Store</bpmn:incoming><bpmn:outgoing>Flow_Store_Wait</bpmn:outgoing>
    </bpmn:serviceTask>
    <bpmn:intermediateCatchEvent id="Event_Demand" name="Work request">
      <bpmn:incoming>Flow_Store_Wait</bpmn:incoming><bpmn:outgoing>Flow_Wait_Retrieve</bpmn:outgoing><bpmn:messageEventDefinition />
    </bpmn:intermediateCatchEvent>
    <bpmn:manualTask id="Task_Retrieve" name="Retrieve from drawer">
      <bpmn:incoming>Flow_Wait_Retrieve</bpmn:incoming><bpmn:outgoing>Flow_Retrieve_Surface</bpmn:outgoing>
    </bpmn:manualTask>
    <bpmn:task id="Task_Surface" name="Place on work surface">
      <bpmn:incoming>Flow_Retrieve_Surface</bpmn:incoming><bpmn:outgoing>Flow_Surface_Human</bpmn:outgoing>
    </bpmn:task>
    <bpmn:userTask id="Task_Human" name="Human interaction">
      <bpmn:incoming>Flow_Surface_Human</bpmn:incoming><bpmn:outgoing>Flow_Human_End</bpmn:outgoing>
    </bpmn:userTask>
    <bpmn:endEvent id="EndEvent_Complete" name="Part completed">
      <bpmn:incoming>Flow_Human_End</bpmn:incoming>
    </bpmn:endEvent>
    <bpmn:sequenceFlow id="Flow_Start_Print" sourceRef="StartEvent_Order" targetRef="Task_Print" />
    <bpmn:sequenceFlow id="Flow_Print_Remove" sourceRef="Task_Print" targetRef="Task_Remove" />
    <bpmn:sequenceFlow id="Flow_Remove_Pick" sourceRef="Task_Remove" targetRef="Task_Pick" />
    <bpmn:sequenceFlow id="Flow_Pick_Color" sourceRef="Task_Pick" targetRef="Task_Color" />
    <bpmn:sequenceFlow id="Flow_Color_Gateway" sourceRef="Task_Color" targetRef="Gateway_Color" />
    <bpmn:sequenceFlow id="Flow_Color_Store" name="yes" sourceRef="Gateway_Color" targetRef="Task_Store" />
    <bpmn:sequenceFlow id="Flow_Color_Recheck" name="no" sourceRef="Gateway_Color" targetRef="Task_Recheck" />
    <bpmn:sequenceFlow id="Flow_Recheck_Color" sourceRef="Task_Recheck" targetRef="Task_Color" />
    <bpmn:sequenceFlow id="Flow_Store_Wait" sourceRef="Task_Store" targetRef="Event_Demand" />
    <bpmn:sequenceFlow id="Flow_Wait_Retrieve" sourceRef="Event_Demand" targetRef="Task_Retrieve" />
    <bpmn:sequenceFlow id="Flow_Retrieve_Surface" sourceRef="Task_Retrieve" targetRef="Task_Surface" />
    <bpmn:sequenceFlow id="Flow_Surface_Human" sourceRef="Task_Surface" targetRef="Task_Human" />
    <bpmn:sequenceFlow id="Flow_Human_End" sourceRef="Task_Human" targetRef="EndEvent_Complete" />
  </bpmn:process>
  <bpmndi:BPMNDiagram id="BPMNDiagram_Production">
    <bpmndi:BPMNPlane id="BPMNPlane_Production" bpmnElement="Process_Production">
      <bpmndi:BPMNShape id="StartEvent_Order_di" bpmnElement="StartEvent_Order"><dc:Bounds x="35" y="162" width="36" height="36" /><bpmndi:BPMNLabel><dc:Bounds x="13" y="204" width="82" height="27" /></bpmndi:BPMNLabel></bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Task_Print_di" bpmnElement="Task_Print"><dc:Bounds x="115" y="140" width="100" height="80" /></bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Task_Remove_di" bpmnElement="Task_Remove"><dc:Bounds x="265" y="140" width="110" height="80" /></bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Task_Pick_di" bpmnElement="Task_Pick"><dc:Bounds x="425" y="140" width="110" height="80" /></bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Task_Color_di" bpmnElement="Task_Color"><dc:Bounds x="585" y="140" width="100" height="80" /></bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Gateway_Color_di" bpmnElement="Gateway_Color" isMarkerVisible="true"><dc:Bounds x="735" y="155" width="50" height="50" /><bpmndi:BPMNLabel><dc:Bounds x="790" y="173" width="86" height="27" /></bpmndi:BPMNLabel></bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Task_Recheck_di" bpmnElement="Task_Recheck"><dc:Bounds x="585" y="25" width="100" height="80" /></bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Task_Store_di" bpmnElement="Task_Store"><dc:Bounds x="710" y="300" width="100" height="80" /></bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Event_Demand_di" bpmnElement="Event_Demand"><dc:Bounds x="624" y="322" width="36" height="36" /><bpmndi:BPMNLabel><dc:Bounds x="606" y="364" width="72" height="14" /></bpmndi:BPMNLabel></bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Task_Retrieve_di" bpmnElement="Task_Retrieve"><dc:Bounds x="465" y="300" width="110" height="80" /></bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Task_Surface_di" bpmnElement="Task_Surface"><dc:Bounds x="305" y="300" width="110" height="80" /></bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Task_Human_di" bpmnElement="Task_Human"><dc:Bounds x="145" y="300" width="110" height="80" /></bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="EndEvent_Complete_di" bpmnElement="EndEvent_Complete"><dc:Bounds x="55" y="322" width="36" height="36" /><bpmndi:BPMNLabel><dc:Bounds x="37" y="364" width="72" height="14" /></bpmndi:BPMNLabel></bpmndi:BPMNShape>
      <bpmndi:BPMNEdge id="Flow_Start_Print_di" bpmnElement="Flow_Start_Print"><di:waypoint x="71" y="180" /><di:waypoint x="115" y="180" /></bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="Flow_Print_Remove_di" bpmnElement="Flow_Print_Remove"><di:waypoint x="215" y="180" /><di:waypoint x="265" y="180" /></bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="Flow_Remove_Pick_di" bpmnElement="Flow_Remove_Pick"><di:waypoint x="375" y="180" /><di:waypoint x="425" y="180" /></bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="Flow_Pick_Color_di" bpmnElement="Flow_Pick_Color"><di:waypoint x="535" y="180" /><di:waypoint x="585" y="180" /></bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="Flow_Color_Gateway_di" bpmnElement="Flow_Color_Gateway"><di:waypoint x="685" y="180" /><di:waypoint x="735" y="180" /></bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="Flow_Color_Store_di" bpmnElement="Flow_Color_Store"><di:waypoint x="760" y="205" /><di:waypoint x="760" y="300" /><bpmndi:BPMNLabel><dc:Bounds x="768" y="249" width="18" height="14" /></bpmndi:BPMNLabel></bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="Flow_Color_Recheck_di" bpmnElement="Flow_Color_Recheck"><di:waypoint x="760" y="155" /><di:waypoint x="760" y="65" /><di:waypoint x="685" y="65" /><bpmndi:BPMNLabel><dc:Bounds x="744" y="108" width="14" height="14" /></bpmndi:BPMNLabel></bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="Flow_Recheck_Color_di" bpmnElement="Flow_Recheck_Color"><di:waypoint x="635" y="105" /><di:waypoint x="635" y="140" /></bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="Flow_Store_Wait_di" bpmnElement="Flow_Store_Wait"><di:waypoint x="710" y="340" /><di:waypoint x="660" y="340" /></bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="Flow_Wait_Retrieve_di" bpmnElement="Flow_Wait_Retrieve"><di:waypoint x="624" y="340" /><di:waypoint x="575" y="340" /></bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="Flow_Retrieve_Surface_di" bpmnElement="Flow_Retrieve_Surface"><di:waypoint x="465" y="340" /><di:waypoint x="415" y="340" /></bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="Flow_Surface_Human_di" bpmnElement="Flow_Surface_Human"><di:waypoint x="305" y="340" /><di:waypoint x="255" y="340" /></bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="Flow_Human_End_di" bpmnElement="Flow_Human_End"><di:waypoint x="145" y="340" /><di:waypoint x="91" y="340" /></bpmndi:BPMNEdge>
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>`;
