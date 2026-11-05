// Compositions (spec §17.15): the full story 1920 × 1080 and a portrait cut 1080 × 1920, 30 fps. The length comes
// from public/timeline.<lang>.json: the sum of the scenes minus the fades that overlap neighbours.
import { type CalculateMetadataFunction, Composition, staticFile } from "remotion";

import { FADE, FPS, sceneFrames, Story } from "./Story";
import type { StoryProps, Timeline } from "./types";

const meta: CalculateMetadataFunction<StoryProps> = async ({ props }) => {
  const timeline = (await fetch(staticFile(`timeline.${props.lang}.json`)).then((r) => r.json())) as Timeline;
  const frames =
    timeline.scenes.reduce((n, s) => n + sceneFrames(s.seconds), 0) - FADE * Math.max(0, timeline.scenes.length - 1);
  return { durationInFrames: Math.max(1, frames), props: { ...props, timeline } };
};

export function RemotionRoot() {
  return (
    <>
      <Composition
        id="KadalMitraStory"
        component={Story}
        width={1920}
        height={1080}
        fps={FPS}
        durationInFrames={1}
        defaultProps={{ lang: "en-IN", layout: "landscape" } as StoryProps}
        calculateMetadata={meta}
      />
      <Composition
        id="KadalMitraStoryVertical"
        component={Story}
        width={1080}
        height={1920}
        fps={FPS}
        durationInFrames={1}
        defaultProps={{ lang: "en-IN", layout: "portrait" } as StoryProps}
        calculateMetadata={meta}
      />
    </>
  );
}
