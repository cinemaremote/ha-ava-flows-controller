# AVA Flows Controller for Home Assistant

Unofficial Home Assistant integration that brings your AVA OS flows into Home Assistant.

Not affiliated with or endorsed by AVA Inc.

## What it does

- Finds your AVA Brain on the network automatically (or add it by IP address).
- Turns each flow into a button you can use in dashboards, automations and scripts.
- Gives AVA's auto-named power-off flows clear names, like "XBOX – Power Off".
- Adds an **AVA Flows** page to the sidebar where you can run flows, give them friendly names, copy each flow's run URL and export the full list as a text file.
- Gives every flow a run URL, so you can start it from other apps and devices.
- Reconnects on its own if the Brain's IP address changes.

Friendly names are stored in Home Assistant only. Nothing is changed on the AVA Brain.

## Requirements

- Home Assistant 2026.2 or newer
- An AVA Brain running AVA OS on the same network as Home Assistant

## Installation (HACS)

1. In Home Assistant, open **HACS**.
2. Open the **⋮** menu in the top-right corner and choose **Custom repositories**.
3. Enter `https://github.com/cinemaremote/ha-ava-flows-controller`, set the type to **Integration**, and click **Add**.
4. Search HACS for **AVA Flows Controller** and click **Download**.
5. Restart Home Assistant.

## Setup

After the restart, Home Assistant shows **AVA OS discovered** under **Settings → Devices & services**. Click **Add**, then **Submit**.

If your Brain isn't discovered, click **Add integration**, search for **AVA Flows Controller**, and enter the Brain's IP address.

Then open **AVA Flows** in the sidebar.

## Options

Under **Settings → Devices & services → AVA Flows Controller → Configure** you can:

- change the Brain's IP address or port
- include or leave out flows that are hidden or disabled in AVA
- choose which flows become buttons
- turn power-off name cleanup on or off
- show or hide the AVA Flows page in the sidebar

## Dashboard card

To put flows on your own dashboard, add a card and choose **AVA Flows**, or use:

```yaml
type: custom:ava-flows-card
```

Optional settings: `title`, `brain`, `room`, `show_power_off: false`.

## Services

- `ava_flows_controller.rename_flow` sets or clears a flow's name in Home Assistant.
- `ava_flows_controller.export_flows` builds the text list of flows and run URLs.
