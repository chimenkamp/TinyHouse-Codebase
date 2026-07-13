/// <reference types="vite/client" />

declare module "urdf-loader" {
  import { LoadingManager, Object3D } from "three";

  export default class URDFLoader {
    constructor(manager?: LoadingManager);
    packages: Record<string, string> | ((packageName: string) => string);
    load(url: string, onLoad: (robot: Object3D & { joints?: Record<string, unknown> }) => void, onProgress?: (event: ProgressEvent) => void, onError?: (event: unknown) => void): void;
  }
}

