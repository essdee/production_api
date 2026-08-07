import * as htmlToImage from "html-to-image";

export async function copyElementAsImage(element) {
    if (!element) {
        throw new Error("Nothing available to copy");
    }
    if (!navigator.clipboard?.write || typeof ClipboardItem === "undefined") {
        throw new Error("Image clipboard is not supported by this browser");
    }

    if (document.activeElement && typeof document.activeElement.blur === "function") {
        document.activeElement.blur();
    }

    const blob = await htmlToImage.toBlob(element, {
        backgroundColor: "#ffffff",
        pixelRatio: 1,
        width: Math.max(element.scrollWidth, element.clientWidth),
        height: Math.max(element.scrollHeight, element.clientHeight),
    });
    if (!blob) {
        throw new Error("Unable to create report image");
    }

    await navigator.clipboard.write([
        new ClipboardItem({ "image/png": blob }),
    ]);
}
