CREATE 
    ALGORITHM = UNDEFINED 
    DEFINER = `root`@`%` 
    SQL SECURITY DEFINER
VIEW `flights`.`ticket_prices` AS
    SELECT 
        `flights`.`raw_market`.`Origin` AS `origin`,
        `flights`.`raw_market`.`Dest` AS `dest`,
        `flights`.`raw_market`.`TkCarrier` AS `carrier`,
        ROUND((SUM((`flights`.`raw_market`.`Passengers` * `flights`.`raw_market`.`MktFare`)) / SUM(`flights`.`raw_market`.`Passengers`)),
                0) AS `fare`,
        ROUND((SUM(((`flights`.`raw_market`.`Passengers` * `flights`.`raw_market`.`MktFare`) / `flights`.`raw_market`.`MktDistance`)) / SUM(`flights`.`raw_market`.`Passengers`)),
                3) AS `fare_per_mile`,
        SUM(`flights`.`raw_market`.`Passengers`) AS `passengers`,
        ROUND(AVG(`flights`.`raw_market`.`MktDistance`),
                0) AS `distance`
    FROM
        `flights`.`raw_market`
    WHERE
        ((`flights`.`raw_market`.`TkCarrier` <> '--')
            AND (`flights`.`raw_market`.`TkCarrier` <> '99'))
    GROUP BY `flights`.`raw_market`.`Origin` , `flights`.`raw_market`.`Dest` , `flights`.`raw_market`.`TkCarrier`
    HAVING ((SUM(`flights`.`raw_market`.`Passengers`) > 20)
        AND (`fare` > 50)
        AND (`fare` < 5000))
    ORDER BY `flights`.`raw_market`.`Origin` , `flights`.`raw_market`.`Dest` , `flights`.`raw_market`.`TkCarrier`
