#!/usr/bin/env python3
import argparse
import sys
import logging
from pathlib import Path

from .config import load_config, validate_config, ConfigError
from .qslmaster_core import QSLProcessor, QSLProcessorError


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    
    formatter = logging.Formatter(
        fmt='%(levelname)-8s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)


def main():
    parser = argparse.ArgumentParser(
        description='QSLMaster - Download QSO from Wavelog for QSL card label preparation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage examples:
  %(prog)s --config config.json -o output.adif
  %(prog)s -c /path/to/config.json --from-date 2024-01-01 --to-date 2024-12-31 -o output.adif
  %(prog)s -c config.json --from-date 2024-06-01 -o output.adif --generate-pdf labels.pdf
        """
    )
    
    parser.add_argument(
        '-c', '--config',
        type=str,
        required=True,
        help='Path to configuration JSON file'
    )
    
    parser.add_argument(
        '--from-date',
        type=str,
        default=None,
        help='Filter QSOs from date (format: YYYY-MM-DD)'
    )
    
    parser.add_argument(
        '--to-date',
        type=str,
        default=None,
        help='Filter QSOs to date (format: YYYY-MM-DD)'
    )
    
    parser.add_argument(
        '-o', '--output-adif',
        type=str,
        required=True,
        help='Path to output ADIF file for QSOs to send'
    )
    
    parser.add_argument(
        '--generate-pdf',
        type=str,
        default=None,
        help='Generate PDF labels and save to specified file (e.g., labels.pdf)'
    )
    
    parser.add_argument(
        '--debug-labels',
        action='store_true',
        help='Draw borders around labels in PDF for debugging alignment'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose mode (more information)'
    )

    args = parser.parse_args()
    setup_logging(verbose=args.verbose)
    
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Loading configuration from: {args.config}")
        config = load_config(args.config)
        validate_config(config)
        logger.info("Configuration loaded and validated")
        
        if args.verbose:
            logger.debug(f"Wavelog URL: {config['wavelog_url']}")
        
        processor = QSLProcessor(config)
        
        result = processor.process(
            from_date=args.from_date,
            to_date=args.to_date,
            output_adif=args.output_adif,
            generate_pdf=args.generate_pdf,
            debug_labels=args.debug_labels,
            preview_pdf=args.verbose,
        )
        
        if not result['success']:
            logger.error(f"Processing failed: {result.get('error')}")
            sys.exit(1)
        
        logger.info(f"Processing completed successfully!")
        logger.info(f"Output ADIF: {result['output_adif']}")
        if result['output_pdf']:
            logger.info(f"Output PDF: {result['output_pdf']}")
        
        sys.exit(0)
        
    except ConfigError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if args.verbose:
            import traceback
            logger.debug(traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    main()
