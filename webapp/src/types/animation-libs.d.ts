declare module "@mojs/core" {
  class Burst {
    constructor(options: Record<string, unknown>);
    el?: HTMLElement;
    replay(): unknown;
  }
  const mojs: { Burst: typeof Burst };
  export default mojs;
}
