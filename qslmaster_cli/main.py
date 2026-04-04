import argparse
import sys
import logging

from .config import load_config, validate_config, ConfigError
from .qslmaster_core import QSLProcessor
from .pdf_labels import normalize_pdf_page_specs, normalize_pdf_page_offsets


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
        description='QSLMaster - Prepare QSL card labels from Wavelog or ADIF file source',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage examples:
    %(prog)s --config config.json -o output.adif
    %(prog)s -c /path/to/config.json --from-date 2024-01-01 --to-date 2024-12-31 -o output.adif
    %(prog)s -c config.json --from-date 2024-06-01 -o output.adif --generate-pdf labels.pdf
    %(prog)s -c config.json --list-stations-only
    %(prog)s -c config.json --station 3 -o output.adif
    %(prog)s -c config.json --callsign-list-mode allow --callsign-pattern SP3ABC --callsign-pattern SP3ABC/* -o output.adif
        """
    )
    
    parser.add_argument(
        '-c', '--config',
        type=str,
        required=True,
        help='Path to configuration JSON file'
    )

    parser.add_argument(
        '--source',
        choices=['wavelog', 'adif_file'],
        default=None,
        help='Override source from config: wavelog or adif_file'
    )

    parser.add_argument(
        '--adif-source',
        dest='adif_source',
        type=str,
        default=None,
        help='Path to source ADIF file (used when source=adif_file)'
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
        '--modes',
        type=str,
        default=None,
        help='Filter QSOs by mode (comma-separated: CW,SSB,AM,FM,FT8,DIGI)'
    )

    parser.add_argument(
        '--callsign-list-mode',
        choices=['off', 'allow', 'block'],
        default=None,
        help='Callsign filter mode: off, allow or block'
    )

    parser.add_argument(
        '--callsign-pattern',
        action='append',
        default=None,
        help='Callsign pattern matched against full callsign, supports wildcards like SP3ABC/*'
    )

    parser.add_argument(
        '--station',
        type=str,
        default='all',
        help='If omitted, all stations are used. To select specific stations, provide station ID or a comma-separated list of station ID.'
    )

    parser.add_argument(
        '--list-stations-only',
        action='store_true',
        help='Return only station list and skip QSO analysis'
    )
    
    parser.add_argument(
        '-o', '--output-adif',
        type=str,
        required=False,
        help='Path to output ADIF file for QSOs to send'
    )
    
    parser.add_argument(
        '--generate-pdf',
        type=str,
        default=None,
        help='Generate PDF labels and save to specified file (e.g., labels.pdf)'
    )

    parser.add_argument(
        '--pdf-page-offsets',
        type=str,
        default=None,
        help='Comma-separated count of already used label slots for consecutive PDF pages, e.g. 4,0,8'
    )

    parser.add_argument(
        '--pdf-page-option',
        action='append',
        default=None,
        help='Per-page PDF options in format offset|skip1,skip2. Repeat for consecutive pages, e.g. --pdf-page-option 4|8,9'
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

    if not args.list_stations_only and not args.output_adif:
        parser.error('--output-adif is required unless --list-stations-only is used')

    if args.list_stations_only and args.generate_pdf:
        parser.error('--generate-pdf cannot be used with --list-stations-only')

    if (args.pdf_page_offsets or args.pdf_page_option) and not args.generate_pdf:
        parser.error('--pdf-page-offsets and --pdf-page-option require --generate-pdf')

    setup_logging(verbose=args.verbose)
    
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Loading configuration from: {args.config}")
        config = load_config(args.config)
        pdf_page_specs = normalize_pdf_page_specs(args.pdf_page_option)
        if not pdf_page_specs and args.pdf_page_offsets:
            pdf_page_specs = [
                {'offset': offset, 'skip_slots': []}
                for offset in normalize_pdf_page_offsets(args.pdf_page_offsets)
            ]

        if args.source:
            config['source'] = args.source
        if args.adif_source:
            config['adif_file_path'] = args.adif_source
        if args.callsign_list_mode is not None:
            config['callsign_filter_mode'] = args.callsign_list_mode
        if args.callsign_pattern is not None:
            config['callsign_filter_patterns'] = args.callsign_pattern

        validate_config(config)
        logger.info("Configuration loaded and validated")

        source = config.get('source', 'wavelog')

        if args.list_stations_only and source != 'wavelog':
            logger.error('--list-stations-only is available only for source=wavelog')
            sys.exit(1)

        if source == 'adif_file' and not str(config.get('adif_file_path', '')).strip():
            logger.error('For source=adif_file provide ADIF file using --adif-source or adif_file_path in config')
            sys.exit(1)
        
        if args.verbose:
            logger.debug(f"Source: {source}")
            if source == 'wavelog':
                logger.debug(f"Wavelog URL: {config.get('wavelog_url', '')}")
            else:
                logger.debug(f"ADIF file path: {config.get('adif_file_path', '')}")
        
        processor = QSLProcessor(config)
        
        station_selectors = [s.strip() for s in args.station.split(',')] if args.station and args.station.lower() != 'all' else ['all']
        result = processor.process(
            from_date=args.from_date,
            to_date=args.to_date,
            modes=args.modes,
            station_selector=station_selectors,
            list_stations_only=args.list_stations_only,
            output_adif=args.output_adif,
            generate_pdf=args.generate_pdf,
            pdf_page_specs=pdf_page_specs,
            debug_labels=args.debug_labels,
            preview_pdf=args.verbose,
        )
        
        if not result['success']:
            logger.error(f"Processing failed: {result.get('error')}")
            sys.exit(1)
        
        if args.list_stations_only:
            stations = result.get('stations', [])
            header = f"{'ID':<4} {'CALL':<8} {'PROFILE':<48} {'STATUS':<8}"
            logger.info(f"Station list:")
            logger.info('-' * len(header))
            logger.info(header)
            logger.info('-' * len(header))
            for station in stations:
                active = 'active' if station.get('station_active') == '1' else 'inactive'
                logger.info(f"{station.get('station_id', ''):<4} "
                            f"{station.get('station_callsign', ''):<8} "
                            f"{station.get('station_profile_name', ''):<48} "
                            f"{active:<8}")
            logger.info('-' * len(header))
            sys.exit(0)

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
