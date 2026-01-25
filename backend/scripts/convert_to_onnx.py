import os
import logging
from pathlib import Path
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def export_to_onnx(model_name: str, output_dir: str, quantize: bool = True):
    """
    Exports a Hugging Face Transformer model to ONNX format and optionally quantizes it.
    
    Args:
        model_name (str): The model ID (e.g., "distilbert-base-uncased-finetuned-sst-2-english").
        output_dir (str): Directory to save the ONNX model.
        quantize (bool): Whether to apply dynamic quantization.
    """
    try:
        from optimum.onnxruntime import ORTModelForSequenceClassification
        from transformers import AutoTokenizer
        from optimum.onnxruntime.configuration import AutoQuantizationConfig
        from optimum.onnxruntime import ORTQuantizer
    except ImportError:
        logger.error("Required libraries not found. Please install: pip install optimum[onnxruntime]")
        return

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Exporting model '{model_name}' to ONNX at {output_dir}...")
    
    # Load and Export
    model = ORTModelForSequenceClassification.from_pretrained(
        model_name, 
        export=True
    )
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    
    logger.info("ONNX export complete.")
    
    if quantize:
        logger.info("Applying Dynamic Quantization...")
        
        # Define quantization configuration
        qconfig = AutoQuantizationConfig.avx512_vnni(is_static=False, per_channel=False)
        
        quantizer = ORTQuantizer.from_pretrained(model)
        
        # Quantize the model
        quantizer.quantize(
            save_dir=output_dir,
            quantization_config=qconfig,
        )
        logger.info(f"Quantized model saved to {output_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert HF Model to ONNX")
    parser.add_argument("--model", type=str, default="distilbert-base-uncased-finetuned-sst-2-english", help="Model ID")
    parser.add_argument("--output", type=str, default="backend/resources/models/sentiment_onnx", help="Output directory")
    parser.add_argument("--no-quantize", action="store_true", help="Disable quantization")
    
    args = parser.parse_args()
    
    # Resolve relative path for default output
    if args.output.startswith("backend/"):
        # Assume running from project root
        base_dir = os.getcwd()
        output_dir = os.path.join(base_dir, args.output)
    else:
        output_dir = args.output

    export_to_onnx(args.model, output_dir, not args.no_quantize)
